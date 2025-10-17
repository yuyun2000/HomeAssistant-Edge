import json
import re
import threading
import time
import wave
import pyaudio
import requests
import queue
import numpy as np
import sounddevice as sd
from chat import ChatBot
from ha_control import control_light, control_curtain,control_fan,control_climate,call_service,control_lock,control_media_player,control_switch
from config import ASR_API_URL, SYSTEM_PROMPT

# 导入KWS和VAD模块
from kws import KeywordSpotter
from vad import SileroVAD

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
            system_message=SYSTEM_PROMPT
        )
        print("sys prompt:",SYSTEM_PROMPT)
        self.recorder = AudioRecorder()
        self.queue = queue.Queue()
        
        # 初始化KWS和VAD
        try:
            self.kws = KeywordSpotter()
            print("Keyword spotter initialized successfully!")
        except Exception as e:
            print(f"Failed to initialize keyword spotter: {e}")
            self.kws = None
            
        try:
            self.vad = SileroVAD("./models/silero-vad.onnx", buffer_size=5, silence_threshold=0.3)
            print("VAD initialized successfully!")
        except Exception as e:
            print(f"Failed to initialize VAD: {e}")
            self.vad = None
    
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
        """Execute homeassistant command using updated ha_control functions"""
        if not command:
            return

        service = command.get("service")
        target_device = command.get("target_device")
        rgb_color = command.get("color", {})
        brightness = command.get("brightness", {})
        position = command.get("position")
        temperature = command.get("temperature")
        fan_mode = command.get("fan_mode")

        if not service or not target_device:
            print("[ERROR] Invalid command format: missing service or target_device.")
            return

        # 解析服务名中的 domain 和具体服务
        try:
            domain, action = service.split('.')
        except ValueError:
            print(f"[ERROR] Invalid service format: '{service}'")
            return
        print("***",domain,target_device,action,"***")
        # 根据 domain 分发到对应的控制函数
        if domain == "light":
            if '(' in rgb_color:
                action = "set_color"
                print("turn action to set_color")
            if action == "turn_on":
                print(brightness)
                control_light(target_device, "on", brightness=brightness)
            elif action == "turn_off":
                control_light(target_device, "off")
            elif action == "set_color":
                control_light(target_device, "color", rgb_color=rgb_color)
            elif action == "get_state":
                result = control_light(target_device, "state")
                print(result)
            else:
                print(f"[ERROR] Unsupported light action: {action}")

        elif domain == "cover":
            if action == "open_cover":
                control_curtain(target_device, "open")
            elif action == "close_cover":
                control_curtain(target_device, "close")
            elif action == "set_position":
                control_curtain(target_device, "position", position=position)
            elif action == "get_state":
                result = control_curtain(target_device, "state")
                print(result)
            else:
                print(f"[ERROR] Unsupported cover action: {action}")

        elif domain == "fan":
            if action == "turn_on":
                control_fan(target_device, "on")
            elif action == "turn_off":
                control_fan(target_device, "off")
            elif action == "increase_speed":
                control_fan(target_device, "increase_speed")
            elif action == "decrease_speed":
                control_fan(target_device, "decrease_speed")
            elif action == "get_state":
                result = control_fan(target_device, "state")
                print(result)
            else:
                print(f"[ERROR] Unsupported fan action: {action}")

        elif domain == "climate":
            if action == "set_temperature":
                
                control_climate(target_device, "set_temperature", temperature=temperature)
            elif action == "set_fan_mode":
                
                control_climate(target_device, "set_fan_mode", fan_mode=fan_mode)
            elif action == "get_state":
                result = control_climate(target_device, "state")
                print(result)
            else:
                print(f"[ERROR] Unsupported climate action: {action}")

        elif domain == "lock":
            if action == "lock":
                control_lock(target_device, "lock")
            elif action == "unlock":
                control_lock(target_device, "unlock")
            elif action == "get_state":
                result = control_lock(target_device, "state")
                print(result)
            else:
                print(f"[ERROR] Unsupported lock action: {action}")

        elif domain == "media_player":
            if action == "media_play":
                control_media_player(target_device, "play")
            elif action == "media_pause":
                control_media_player(target_device, "pause")
            elif action == "media_stop":
                control_media_player(target_device, "stop")
            elif action == "get_state":
                result = control_media_player(target_device, "state")
                print(result)
            else:
                print(f"[ERROR] Unsupported media player action: {action}")

        elif domain == "switch":
            if action == "turn_on":
                control_switch(target_device, "on")
            elif action == "turn_off":
                control_switch(target_device, "off")
            elif action == "get_state":
                result = control_switch(target_device, "state")
                print(result)
            else:
                print(f"[ERROR] Unsupported switch action: {action}")

        else:
            print(f"[ERROR] Unsupported domain: {domain}")
            
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
    
    def process_voice_command(self):
        """Process voice command using KWS and VAD"""
        if not self.kws or not self.vad:
            print("KWS or VAD not initialized, cannot process voice command")
            return
            
        print("Listening for wake word...")
        
        # 音频参数
        sample_rate = 16000
        kws_samples_per_read = int(0.1 * sample_rate)  # 0.1 second = 100 ms
        vad_samples_per_read = 512  # VAD窗口大小
        
        # 打开音频输入流
        with sd.InputStream(channels=1, dtype="float32", samplerate=sample_rate) as stream:
            while True:
                # 读取音频数据用于KWS
                samples, _ = stream.read(kws_samples_per_read)
                samples = samples.reshape(-1)
                
                # 处理音频数据，检测关键词
                keyword = self.kws.process_audio(samples)
                
                # 如果检测到关键词
                if keyword:
                    print(f"Detected wake word: {keyword}")
                    print("Listening for voice command...")
                    
                    # 开始录音
                    self.recorder.start_recording()
                    
                    # 使用VAD检测语音活动
                    silence_count = 0
                    # 唤醒后等待用户说话的最大静默计数（约10秒）
                    initial_max_silence_count = 320
                    # 用户说话过程中的静默计数阈值（约1.6秒）
                    speaking_max_silence_count = 50
                    max_silence_count = initial_max_silence_count  # 初始使用较长的静默容忍时间
                    speaking_detected = False  # 标记是否检测到用户说话
                    
                    # 重置VAD缓冲区
                    if hasattr(self.vad, 'prob_buffer'):
                        self.vad.prob_buffer.clear()
                    
                    while True:
                        # 读取音频数据用于VAD
                        audio_samples, _ = stream.read(vad_samples_per_read)
                        audio_samples = audio_samples.flatten()
                        
                        # 检查是否在说话
                        is_speaking = self.vad(audio_samples)
                        
                        if not is_speaking:
                            silence_count += 1
                            if silence_count > max_silence_count:
                                # 停止录音
                                filename = self.recorder.stop_recording()
                                if filename:
                                    text = self.recognize_speech(filename)
                                    if text:
                                        print(f"\nYou said: {text}")
                                        # 处理识别到的文本
                                        content = self.bot.chat(text)
                                        print(f"\nAssistant: {content}")
                                        t = self.bot.chat("reset")
                                        # 解析并执行命令
                                        command = self.parse_response(content)
                                        if command:
                                            print(f"Executing: {command}")
                                            self.execute_command(command)
                                break
                        else:
                            # 检测到说话
                            silence_count = 0  # 重置静默计数
                            if not speaking_detected:
                                # 首次检测到说话，切换到较短的静默容忍时间
                                speaking_detected = True
                                max_silence_count = speaking_max_silence_count
                    
                    # 重置KWS流
                    self.kws.reset()
                    print("Listening for wake word...")
    
    def run(self):
        """Main interactive loop with speech recognition"""
        print("Home Assistant Controller - Listening for wake word (Press Ctrl+C to exit)")
        
        try:
            # 启动语音命令处理
            self.process_voice_command()
        except KeyboardInterrupt:
            print("\nCaught Ctrl + C. Exiting")
        finally:
            # Clean up audio resources
            if self.recorder.recording:
                self.recorder.stop_recording()
            self.recorder.p.terminate()
            if self.kws:
                self.kws.close()

if __name__ == "__main__":
    from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, SYSTEM_PROMPT

    controller = HomeAssistantController(
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
        model=LLM_MODEL
    )
    controller.run()
