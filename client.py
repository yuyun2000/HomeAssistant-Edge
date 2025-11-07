import socket
import json
import time
import threading
import uuid
import numpy as np
import sounddevice as sd
from kws import KeywordSpotter
from vad import SileroVAD
from collections import OrderedDict

class SmartVoiceClient:
    """智能语音客户端 - 本地运行KWS和VAD，只发送命令片段"""
    
    def __init__(self, server_host, server_port=9999):
        self.server_host = server_host
        self.server_port = server_port
        self.socket = None
        self.connected = False
        
        # 请求追踪
        self.pending_requests = OrderedDict()  # {request_id: {'timestamp': xxx, 'audio_size': xxx}}
        self.request_lock = threading.Lock()
        
        # 音频参数
        self.sample_rate = 16000
        self.channels = 1
        
        # 接收线程
        self.receive_thread = None
        self.should_receive = False
        
        # 初始化KWS和VAD
        try:
            self.kws = KeywordSpotter()
            print("✅ KWS initialized")
        except Exception as e:
            print(f"❌ KWS init failed: {e}")
            self.kws = None
        
        try:
            self.vad = SileroVAD("./models/silero-vad.onnx", buffer_size=5, silence_threshold=0.3)
            print("✅ VAD initialized")
        except Exception as e:
            print(f"❌ VAD init failed: {e}")
            self.vad = None
    
    def connect(self):
        """连接到服务器"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_host, self.server_port))
            self.connected = True
            print(f"✅ Connected to {self.server_host}:{self.server_port}")
            
            # 启动接收线程
            self.should_receive = True
            self.receive_thread = threading.Thread(target=self.receive_loop, daemon=True)
            self.receive_thread.start()
            
            # 测试连接
            test_id = str(uuid.uuid4())
            self.send_message('PING', {}, request_id=test_id)
            time.sleep(0.5)  # 等待PONG响应
            
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            self.connected = False
            return False
    
    def send_message(self, msg_type, data, audio_data=None, request_id=None):
        """发送消息到服务器"""
        if not request_id:
            request_id = str(uuid.uuid4())
        
        try:
            header = {
                'type': msg_type,
                'request_id': request_id,
                'timestamp': time.time()
            }
            
            if msg_type == 'VOICE_COMMAND' and audio_data:
                header['size'] = len(audio_data)
                header['sample_rate'] = self.sample_rate
                header['channels'] = self.channels
                header['duration'] = len(audio_data) / (self.sample_rate * 2)
                
                # 记录pending请求
                with self.request_lock:
                    self.pending_requests[request_id] = {
                        'timestamp': time.time(),
                        'audio_size': len(audio_data),
                        'type': msg_type
                    }
            
            header.update(data)
            
            # 发送头部
            header_json = json.dumps(header, ensure_ascii=False).encode('utf-8')
            header_size = len(header_json).to_bytes(4, 'big')
            self.socket.sendall(header_size + header_json)
            
            # 如果有音频数据，分块发送
            if audio_data:
                total_sent = 0
                chunk_size = 8192
                while total_sent < len(audio_data):
                    chunk = audio_data[total_sent:total_sent + chunk_size]
                    self.socket.sendall(chunk)
                    total_sent += len(chunk)
                
                print(f"📤 Sent audio: {len(audio_data)} bytes (ID: {request_id[:8]})")
            
            return request_id
        except Exception as e:
            print(f"❌ Send error: {e}")
            self.connected = False
            return None
    
    def receive_loop(self):
        """持续接收服务器响应的线程"""
        while self.should_receive and self.connected:
            try:
                response = self.receive_response(timeout=0.5)
                if response:
                    self.handle_response(response)
            except socket.timeout:
                continue
            except Exception as e:
                if self.should_receive:
                    print(f"❌ Receive loop error: {e}")
                break
    
    def receive_response(self, timeout=0.5):
        """接收服务器响应"""
        try:
            self.socket.settimeout(timeout)
            
            # 接收响应长度
            size_data = self.socket.recv(4)
            if not size_data or len(size_data) < 4:
                return None
            
            response_size = int.from_bytes(size_data, 'big')
            
            # 接收响应内容
            response_data = b''
            while len(response_data) < response_size:
                chunk = self.socket.recv(min(4096, response_size - len(response_data)))
                if not chunk:
                    break
                response_data += chunk
            
            if len(response_data) < response_size:
                return None
            
            response = json.loads(response_data.decode('utf-8'))
            return response
        except socket.timeout:
            raise
        except Exception as e:
            if self.should_receive:
                print(f"❌ Receive error: {e}")
            return None
    
    def start_listening(self):
        """开始监听唤醒词"""
        if not self.kws or not self.vad:
            print("❌ KWS or VAD not available")
            return
        
        if not self.connected:
            print("❌ Not connected to server")
            return
        
        print("\n🎤 Listening for wake word...")
        print("   (Press Ctrl+C to exit)\n")
        
        kws_chunk_size = int(0.1 * self.sample_rate)  # 100ms
        vad_chunk_size = 512
        
        try:
            with sd.InputStream(channels=1, dtype='float32', samplerate=self.sample_rate) as stream:
                # 状态机
                STATE_WAKE = 'WAKE'
                STATE_RECORDING = 'RECORDING'
                state = STATE_WAKE
                
                recording_frames = []
                silence_count = 0
                speech_frames = 0
                initial_silence_limit = 300  # 10秒
                speaking_silence_limit = 21   # 0.7秒
                max_silence = initial_silence_limit
                
                while self.connected:
                    if state == STATE_WAKE:
                        # 唤醒词检测
                        audio_chunk, _ = stream.read(kws_chunk_size)
                        audio_chunk = audio_chunk.flatten()
                        
                        keyword = self.kws.process_audio(audio_chunk)
                        
                        if keyword:
                            print(f"🎯 Wake word: {keyword}")
                            print("🎙️ Listening...")
                            
                            state = STATE_RECORDING
                            recording_frames = []
                            silence_count = 0
                            speech_frames = 0
                            max_silence = initial_silence_limit
                            self.vad.prob_buffer.clear()
                            start_time = time.time()
                    
                    elif state == STATE_RECORDING:
                        # 录制命令
                        audio_chunk, _ = stream.read(vad_chunk_size)
                        audio_chunk = audio_chunk.flatten()
                        
                        # 转换为int16存储
                        int16_chunk = (audio_chunk * 32767).astype(np.int16)
                        recording_frames.append(int16_chunk.tobytes())
                        
                        # VAD检测
                        is_speaking = self.vad(audio_chunk)
                        
                        if not is_speaking:
                            silence_count += 1
                            if silence_count > max_silence:
                                # 录音结束
                                duration = time.time() - start_time
                                print(f"⏹️ Recorded {duration:.2f}s")
                                
                                # 合并音频数据
                                audio_data = b''.join(recording_frames)
                                
                                # 发送到服务器处理
                                request_id = self.send_message('VOICE_COMMAND', {}, audio_data)
                                if request_id:
                                    print(f"⏳ Waiting for response... (ID: {request_id[:8]})")
                                
                                # 重置状态
                                state = STATE_WAKE
                                self.kws.reset()
                                print("\n🎤 Listening for wake word...\n")
                        else:
                            silence_count = 0
                            speech_frames += 1
                            if speech_frames > 25:
                                max_silence = speaking_silence_limit
        
        except KeyboardInterrupt:
            print("\n🛑 Stopping...")
        finally:
            self.disconnect()
    
    def handle_response(self, response):
        """处理服务器响应"""
        if not response:
            return
        
        msg_type = response.get('type')
        data = response.get('data')
        request_id = response.get('request_id')
        
        # 检查是否是pending的请求
        with self.request_lock:
            if request_id and request_id in self.pending_requests:
                request_info = self.pending_requests[request_id]
                latency = time.time() - request_info['timestamp']
            else:
                latency = None
        
        if msg_type == 'ACK':
            print(f"✓ Server received audio (ID: {request_id[:8] if request_id else 'N/A'})")
        
        elif msg_type == 'ASR_RESULT':
            text = data.get('text') if isinstance(data, dict) else data
            asr_time = data.get('asr_time', 0) if isinstance(data, dict) else 0
            print(f"📝 You said: \"{text}\"")
            print(f"   ASR time: {asr_time}s")
        
        elif msg_type == 'SUCCESS':
            print(f"✅ Command executed!")
            print(f"   Text: {data.get('text')}")
            print(f"   Command: {data.get('command')}")
            print(f"   Status: {data.get('execution_status')}")
            print(f"   Timing: ASR={data.get('asr_time')}s, LLM={data.get('llm_time')}s, Total={data.get('total_time')}s")
            if latency:
                print(f"   Round-trip: {latency:.2f}s")
            
            # 清除pending请求
            with self.request_lock:
                if request_id in self.pending_requests:
                    del self.pending_requests[request_id]
        
        elif msg_type == 'INFO':
            print(f"ℹ️ {data.get('message')}")
            print(f"   Text: {data.get('text')}")
            print(f"   Response: {data.get('response')[:100]}...")
            
            with self.request_lock:
                if request_id in self.pending_requests:
                    del self.pending_requests[request_id]
        
        elif msg_type == 'ERROR':
            error_msg = data if isinstance(data, str) else str(data)
            print(f"❌ Error: {error_msg}")
            
            with self.request_lock:
                if request_id in self.pending_requests:
                    del self.pending_requests[request_id]
        
        elif msg_type == 'PONG':
            pass  # 静默处理心跳
    
    def disconnect(self):
        """断开连接"""
        self.should_receive = False
        self.connected = False
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        
        if self.kws:
            self.kws.close()
        
        print("👋 Disconnected")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python client.py <server_ip> [port]")
        print("Example: python client.py 192.168.1.100")
        sys.exit(1)
    
    server_ip = sys.argv[1]
    server_port = int(sys.argv[2]) if len(sys.argv) > 2 else 9999
    
    client = SmartVoiceClient(server_ip, server_port)
    if client.connect():
        client.start_listening()