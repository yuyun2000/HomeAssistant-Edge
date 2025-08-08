import json
import re
import keyboard
import threading
import time
import wave
import pyaudio
import requests
import queue
from chat import ChatBot, system_prompt
from ha_control import control_light, control_curtain
from config import ASR_API_URL

class AudioRecorder:
    def __init__(self):
        self.recording = False
        self.frames = []
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000

    def start_recording(self):
        """Start audio recording"""
        if self.recording:
            return
            
        self.recording = True
        self.frames = []
        self.stream = self.p.open(format=self.FORMAT,
                                  channels=self.CHANNELS,
                                  rate=self.RATE,
                                  input=True,
                                  frames_per_buffer=self.CHUNK)
        print("Recording started...")
        threading.Thread(target=self.record).start()

    def record(self):
        """Audio recording thread"""
        while self.recording:
            data = self.stream.read(self.CHUNK)
            self.frames.append(data)

    def stop_recording(self):
        """Stop audio recording and save to file"""
        if not self.recording:
            return None
            
        self.recording = False
        time.sleep(0.1)  # Allow last buffer to be captured
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        
        # Save to temporary WAV file
        filename = "temp_recording.wav"
        wf = wave.open(filename, 'wb')
        wf.setnchannels(self.CHANNELS)
        wf.setsampwidth(self.p.get_sample_size(self.FORMAT))
        wf.setframerate(self.RATE)
        wf.writeframes(b''.join(self.frames))
        wf.close()
        print("Recording stopped")
        return filename

class HomeAssistantController:
    def __init__(self, api_key, base_url, model):
        self.bot = ChatBot(
            api_key=api_key,
            base_url=base_url,
            model=model,
            system_message=system_prompt
        )
        self.recorder = AudioRecorder()
        self.recording_started = False
        self.queue = queue.Queue()
    
    def parse_response(self, response: str) -> dict:
        """Extract homeassistant command from LLM response"""
        pattern = r"```homeassistant\n({.*?})\n```"
        match = re.search(pattern, response, re.DOTALL)
        if not match:
            return None
        
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    
    def execute_command(self, command: dict):
        """Execute homeassistant command using ha_control"""
        if not command:
            return
        
        service = command.get("service")
        device = command.get("target_device")
        
        if not service or not device:
            print("Invalid command format")
            return
        
        # Map service to control function
        if service == "light.turn_on":
            control_light(device, "on")
        elif service == "light.turn_off":
            control_light(device, "off")
        elif service == "cover.open":
            control_curtain(device, "position", position=100)
        elif service == "cover.close":
            control_curtain(device, "position", position=0)
        else:
            print(f"Unsupported service: {service}")
            
    def recognize_speech(self, filename):
        """Send audio to ASR API and return recognized text"""
        try:
            with open(filename, "rb") as f:
                files = {"audio": (filename, f, "audio/wav")}
                response = requests.post(ASR_API_URL, files=files, timeout=10)
                response.raise_for_status()
                result = response.json()
                return result.get('text', '')
        except Exception as e:
            print(f"[ASR ERROR] {str(e)}")
            return None
    
    def on_press(self, event):
        """Toggle recording with space key press"""
        if event.name == 'space':
            if not self.recording_started:
                # Start recording
                self.recording_started = True
                self.recorder.start_recording()
            else:
                # Stop recording
                self.recording_started = False
                filename = self.recorder.stop_recording()
                if filename:
                    text = self.recognize_speech(filename)
                    if text:
                        print(f"\nYou said: {text}")
                        self.queue.put(text)
    
    def run(self):
        """Main interactive loop with speech recognition"""
        print("Home Assistant Controller - Press SPACE to start/stop recording")
        keyboard.on_press(self.on_press)
        
        try:
            while True:
                if keyboard.is_pressed('esc'):
                    print("Goodbye!")
                    break
                
                try:
                    # Get recognized text from queue
                    text = self.queue.get(timeout=0.1)
                    if text.lower() in ['exit', 'quit']:
                        print("Goodbye!")
                        break
                    
                    # Get LLM response
                    content = self.bot.chat(text)
                    print(f"\nAssistant: {content}")
                    
                    # Parse and execute command
                    command = self.parse_response(content)
                    if command:
                        print(f"Executing: {command}")
                        self.execute_command(command)
                
                except queue.Empty:
                    # No new speech recognized, continue
                    pass
        finally:
            keyboard.unhook_all()
            # Clean up audio resources
            if self.recorder.recording:
                self.recorder.stop_recording()
            self.recorder.p.terminate()

if __name__ == "__main__":
    from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

    controller = HomeAssistantController(
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
        model=LLM_MODEL
    )
    controller.run()
