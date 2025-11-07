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
    
    def parse_response(self, response: str) -> list:
        """
        Extract homeassistant commands from LLM response
        Returns a list of command dictionaries
        """
        commands = []
        
        # 匹配 ```homeassistant ... ``` 代码块
        pattern = r"```homeassistant\n(.*?)\n```"
        matches = re.findall(pattern, response, re.DOTALL)
        
        if not matches:
            return commands
        
        for match in matches:
            # 处理代码块中的内容，可能包含多个 JSON 对象
            # 按行分割
            lines = match.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    # 尝试解析每一行作为 JSON
                    command = json.loads(line)
                    commands.append(command)
                except json.JSONDecodeError as e:
                    print(f"[WARNING] Failed to parse command: {line}")
                    print(f"[WARNING] JSON Error: {e}")
                    continue
        
        return commands
    
    def execute_command(self, command: dict):
        """Execute a single homeassistant command"""
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
        
        print(f"[EXEC] Domain: {domain}, Device: {target_device}, Action: {action}")
        
        # 根据 domain 分发到对应的控制函数
        if domain == "light":
            if '(' in str(rgb_color):
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
    
    def execute_commands(self, commands: list):
        """Execute multiple homeassistant commands in sequence"""
        if not commands:
            print("[INFO] No commands to execute")
            return
        
        print(f"[INFO] Executing {len(commands)} command(s)...")
        for idx, command in enumerate(commands, 1):
            print(f"\n[Command {idx}/{len(commands)}]")
            self.execute_command(command)
            # 可选：添加命令之间的延迟，避免执行过快
            if idx < len(commands):
                time.sleep(0.1)
        print(f"\n[INFO] All commands executed")
            
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
                    
                    # === 记录用户说话起始时间 ===
                    start_speaking_time = time.time()
                    
                    # 开始录音
                    self.recorder.start_recording()
                    
                    # 使用VAD检测语音活动
                    silence_count = 0
                    initial_max_silence_count = 300  # 约10秒
                    speaking_max_silence_count = 21   # 约0.7s
                    speech_frames = 0 # 说话的语音帧数
                    max_silence_count = initial_max_silence_count
                    
                    # 重置VAD缓冲区
                    if hasattr(self.vad, 'prob_buffer'):
                        self.vad.prob_buffer.clear()
                    
                    while True:
                        audio_samples, _ = stream.read(vad_samples_per_read)
                        audio_samples = audio_samples.flatten()
                        is_speaking = self.vad(audio_samples)
                        
                        if not is_speaking:
                            silence_count += 1
                            if silence_count > max_silence_count:
                                # 停止录音
                                filename = self.recorder.stop_recording()
                                
                                # === 用户说话结束时间 ===
                                end_speaking_time = time.time()
                                user_speech_duration = end_speaking_time - start_speaking_time
                                print(f"[Timing] User speech duration: {user_speech_duration:.2f} seconds")
                                
                                if filename:
                                    # === ASR识别开始时间 ===
                                    asr_start_time = time.time()
                                    text = self.recognize_speech(filename)
                                    # === ASR识别结束时间 ===
                                    asr_end_time = time.time()
                                    asr_duration = asr_end_time - asr_start_time
                                    print(f"[Timing] ASR recognition time: {asr_duration:.2f} seconds")
                                    
                                    if text:
                                        print(f"\nYou said: {text}")
                                        
                                        # === LLM响应开始时间 ===
                                        llm_start_time = time.time()
                                        content = self.bot.chat(text)
                                        # === LLM响应结束时间 ===
                                        llm_end_time = time.time()
                                        llm_duration = llm_end_time - llm_start_time
                                        print(f"[Timing] LLM response time: {llm_duration:.2f} seconds")
                                        
                                        print(f"\nAssistant: {content}")
                                        self.bot.chat("reset")
                                        
                                        # 解析并执行命令（支持多个命令）
                                        commands = self.parse_response(content)
                                        if commands:
                                            self.execute_commands(commands)
                                        else:
                                            print("[INFO] No valid commands found in response")
                                break
                        else:
                            silence_count = 0
                            speech_frames += 1
                            # 如果说话时长大于1.2秒，认为是正常发言，停顿0.7秒后就进入asr阶段
                            if speech_frames > 25:
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
