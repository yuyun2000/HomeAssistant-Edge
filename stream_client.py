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
import struct

class StreamingVoiceClient:
    def __init__(self, server_host, server_port=9999):
        self.server_host = server_host
        self.server_port = server_port
        self.socket = None
        self.connected = False
        
        # 状态控制
        self.pending_requests = OrderedDict()
        self.request_lock = threading.Lock()
        
        # 音频参数
        self.sample_rate = 16000
        
        # 接收线程
        self.receive_thread = None
        self.should_receive = False
        
        # AI 模型
        try:
            self.kws = KeywordSpotter()
            print("✅ KWS initialized")
        except:
            self.kws = None
            print("❌ KWS init failed")
        
        try:
            self.vad = SileroVAD("./models/silero-vad.onnx", buffer_size=5, silence_threshold=0.3)
            print("✅ VAD initialized")
        except:
            self.vad = None
            print("❌ VAD init failed")

    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_host, self.server_port))
            self.connected = True
            print(f"✅ Connected to {self.server_host}:{self.server_port}")
            
            self.should_receive = True
            self.receive_thread = threading.Thread(target=self.receive_loop, daemon=True)
            self.receive_thread.start()
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            self.connected = False
            return False

    # === 流式协议核心发送方法 ===
    
    def send_stream_header(self, request_id):
        """步骤1: 发送流式请求头 (size=0)"""
        header = {
            'type': 'VOICE_COMMAND',
            'request_id': request_id,
            'timestamp': time.time(),
            'size': 0,  # 关键：0 代表流式传输
            'sample_rate': self.sample_rate,
            'channels': 1
        }
        header_json = json.dumps(header, ensure_ascii=False).encode('utf-8')
        # 发送头长度(4 bytes) + 头内容
        self.socket.sendall(len(header_json).to_bytes(4, 'big') + header_json)
        print(f"📡 Stream started (ID: {request_id[:8]})")

    def send_stream_chunk(self, audio_chunk_bytes):
        """步骤2: 发送音频分片"""
        # 协议: [4字节长度] + [数据]
        length = len(audio_chunk_bytes)
        self.socket.sendall(length.to_bytes(4, 'big') + audio_chunk_bytes)

    def finish_stream(self):
        """步骤3: 发送结束标记"""
        # 协议: [0000] (4字节的0)
        self.socket.sendall((0).to_bytes(4, 'big'))
        print("🛑 Stream finished")

    # ==========================

    def start_listening(self):
        if not self.connected or not self.kws: return
        
        print("\n🎤 Ready. Say 'Hi' to wake up...")
        
        kws_chunk = int(0.1 * self.sample_rate) # 100ms for KWS
        vad_chunk = 512                         # ~32ms for VAD
        
        STATE_WAKE = 0
        STATE_STREAMING = 1
        state = STATE_WAKE
        
        current_request_id = None
        silence_count = 0
        max_silence = 300 # 初始静音容忍度
        
        with sd.InputStream(channels=1, samplerate=self.sample_rate, dtype='float32') as stream:
            while self.connected:
                # --- 唤醒检测阶段 ---
                if state == STATE_WAKE:
                    data, _ = stream.read(kws_chunk)
                    data = data.flatten()
                    if self.kws.process_audio(data):
                        print("⚡ Wake Word Detected! Streaming...")
                        
                        # 初始化新的一轮对话
                        state = STATE_STREAMING
                        current_request_id = str(uuid.uuid4())
                        self.vad.prob_buffer.clear()
                        silence_count = 0
                        max_silence = 300 # 初始可以等10秒
                        
                        # 1. 立即告诉服务端：我要开始说话了
                        self.send_stream_header(current_request_id)
                        
                        # 记录开始时间
                        with self.request_lock:
                            self.pending_requests[current_request_id] = {
                                'timestamp': time.time(), 'type': 'VOICE_COMMAND'
                            }

                # --- 边录边传阶段 ---
                elif state == STATE_STREAMING:
                    # 读取一小块
                    data, _ = stream.read(vad_chunk)
                    data = data.flatten()
                    
                    # 转 int16 并发送
                    int16_data = (data * 32767).astype(np.int16).tobytes()
                    self.send_stream_chunk(int16_data) # <--- 核心：直接发出去，不存本地
                    
                    # VAD 检测
                    is_speaking = self.vad(data)
                    
                    if is_speaking:
                        silence_count = 0
                        # 一旦检测到说话，后续静音阈值缩短（比如由10秒变成0.7秒断句）
                        max_silence = 21 
                    else:
                        silence_count += 1
                        
                    # 判断静音超时 -> 结束录音
                    if silence_count > max_silence:
                        self.finish_stream() # <--- 核心：发送结束帧
                        state = STATE_WAKE
                        self.kws.reset()
                        print("⏳ Waiting for server response...\n")

    def receive_loop(self):
        """接收服务端响应（和之前逻辑类似，略微简化）"""
        while self.should_receive:
            try:
                # 读4字节长度
                len_bytes = self.recv_bytes(4)
                if not len_bytes: break
                msg_len = int.from_bytes(len_bytes, 'big')
                
                # 读内容
                msg_bytes = self.recv_bytes(msg_len)
                resp = json.loads(msg_bytes.decode('utf-8'))
                self.handle_response(resp)
            except Exception:
                break
    
    def recv_bytes(self, n):
        data = b''
        while len(data) < n:
            chunk = self.socket.recv(n - len(data))
            if not chunk: return None
            data += chunk
        return data

    def handle_response(self, resp):
        rid = resp.get('request_id')
        msg_type = resp.get('type')
        
        # 计算耗时
        latency = "N/A"
        with self.request_lock:
            if rid in self.pending_requests:
                start_time = self.pending_requests[rid]['timestamp']
                latency = f"{time.time() - start_time:.2f}s"
                if msg_type in ['SUCCESS', 'ERROR']:
                    del self.pending_requests[rid]

        if msg_type == 'ASR_RESULT':
            print(f"📝 ASR Real-time: {resp['data'].get('text')} (Latency: {latency})")
        elif msg_type == 'SUCCESS':
            print(f"🤖 LLM Response: {resp['data'].get('response')[:50]}...")
            print(f"🚀 Command: {resp['data'].get('command')}")
            print(f"⏱️ Total Latency: {latency}")

if __name__ == "__main__":
    client = StreamingVoiceClient('192.168.3.3', 9999)
    if client.connect():
        try:
            client.start_listening()
        except KeyboardInterrupt:
            print("\nExit.")