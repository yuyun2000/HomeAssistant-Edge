import socket
import threading
import wave
import time
import json
import uuid
from main import HomeAssistantController
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

import string
def normalize(s: str) -> str:
    trans = str.maketrans({p: " " for p in r"""!"#$%&()*+,-./:;<=>?@[\]^_`{|}~"""})
    return " ".join(s.lower().translate(trans).split())
class LightweightVoiceServer:
    """轻量级语音控制服务器 - 只处理语音命令，不处理唤醒"""
    
    def __init__(self, host='0.0.0.0', port=9999):
        self.host = host
        self.port = port
        
        # 为每个客户端创建独立的Controller实例，避免对话上下文混乱
        self.client_controllers = {}
        self.controller_lock = threading.Lock()
        
        self.server_socket = None
        self.active_clients = {}
        
    def get_controller(self, client_id):
        """获取或创建客户端专属的Controller"""
        with self.controller_lock:
            if client_id not in self.client_controllers:
                self.client_controllers[client_id] = HomeAssistantController(
                    api_key=LLM_API_KEY,
                    base_url=LLM_BASE_URL,
                    model=LLM_MODEL
                )
                print(f"[{client_id}] Created dedicated controller")
            return self.client_controllers[client_id]
    
    def start(self):
        """启动服务器"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(10)
        
        print(f" Lightweight Voice Server started on {self.host}:{self.port}")
        print(f" Waiting for clients...")
        
        try:
            while True:
                client_socket, address = self.server_socket.accept()
                client_id = f"{address[0]}:{address[1]}"
                print(f"✅ Client connected: {client_id}")
                
                # 为每个客户端创建独立线程处理
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address, client_id),
                    daemon=True
                )
                client_thread.start()
                
                self.active_clients[client_id] = {
                    'socket': client_socket,
                    'address': address,
                    'connected_at': time.time()
                }
                
        except KeyboardInterrupt:
            print("\n Server shutting down...")
        finally:
            if self.server_socket:
                self.server_socket.close()

    def recv_exact(self, sock, count):
        buf = b''
        while len(buf) < count:
            newbuf = sock.recv(count - len(buf))
            if not newbuf: return None
            buf += newbuf
        return buf
    
    def handle_client(self, client_socket, address, client_id):
        """处理客户端请求"""
        try:
            while True:
                # 1. 接收消息头长度 (4字节)
                header_size_bytes = self.recv_exact(client_socket, 4)
                if not header_size_bytes: break
                
                header_length = int.from_bytes(header_size_bytes, 'big')
                
                # 2. 接收消息头 JSON
                header_data = self.recv_exact(client_socket, header_length)
                if not header_data: break
                
                header = json.loads(header_data.decode('utf-8'))
                msg_type = header.get('type')
                request_id = header.get('request_id', str(uuid.uuid4()))
                
                print(f"[{client_id}] Received {msg_type} (ID: {request_id[:8]})")
                
                if msg_type == 'HEARTBEAT':
                    self.send_response(client_socket, 'PONG', 'alive', request_id)
                    
                elif msg_type == 'VOICE_COMMAND':
                    # === 核心修改部分开始 ===
                    audio_size = header.get('size', 0) # 如果是 0 或 -1，代表流式传输
                    
                    audio_data = bytearray()
                    
                    if audio_size > 0:
                        # --- 兼容旧模式：一次性接收固定长度 ---
                        print(f"[{client_id}] Receiving fixed audio: {audio_size} bytes")
                        data = self.recv_exact(client_socket, audio_size)
                        if not data:
                            print(f"[{client_id}] Connection lost during audio recv")
                            break
                        audio_data.extend(data)
                    else:
                        # --- 新模式：流式接收 (Chunked) ---
                        # C++ 客户端逻辑：循环发送 [4字节长度][数据]，最后发送 [0000] 结束
                        print(f"[{client_id}] Receiving streamed audio...")
                        chunk_count = 0
                        while True:
                            # 1. 读分片长度
                            chunk_len_bytes = self.recv_exact(client_socket, 4)
                            if not chunk_len_bytes: break
                            
                            chunk_len = int.from_bytes(chunk_len_bytes, 'big')
                            
                            # 2. 如果长度为0，表示传输结束
                            if chunk_len == 0:
                                print(f"[{client_id}] End of stream signal received.")
                                break
                                
                            # 3. 读分片数据
                            chunk = self.recv_exact(client_socket, chunk_len)
                            if not chunk: break
                            
                            audio_data.extend(chunk)
                            chunk_count += 1
                            # 可选：打印一下进度，防止看起来像卡死
                            if chunk_count % 10 == 0:
                                print(f"[{client_id}] .. received {chunk_count} chunks, total {len(audio_data)} bytes")

                    # === 核心修改部分结束 ===
                    
                    final_size = len(audio_data)
                    print(f"[{client_id}] Audio received completely. Total: {final_size} bytes")
                    
                    if final_size == 0:
                         self.send_response(client_socket, 'ERROR', 'Empty audio', request_id)
                         continue

                    # 立即发送ACK
                    self.send_response(client_socket, 'ACK', 'Audio received', request_id)
                    
                    # 转回 bytes 类型供后续处理
                    self.process_voice_command(client_socket, client_id, bytes(audio_data), header, request_id)
                
                elif msg_type == 'PING':
                    self.send_response(client_socket, 'PONG', 'Server is alive', request_id)
                
                else:
                    print(f"[{client_id}]  Unknown message type: {msg_type}")
        
        except ConnectionResetError:
            print(f"[{client_id}] Connection reset by client")
        except Exception as e:
            print(f"[{client_id}]  Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            client_socket.close()
            if client_id in self.active_clients:
                del self.active_clients[client_id]
            if client_id in self.client_controllers:
                del self.client_controllers[client_id]
            print(f"[{client_id}]  Client disconnected")
    
    def process_voice_command(self, client_socket, client_id, audio_data, header, request_id):
        """处理语音命令：ASR + LLM + 执行"""
        try:
            # 获取客户端专属controller
            controller = self.get_controller(client_id)
            
            # 保存为临时WAV文件
            timestamp = int(time.time() * 1000)
            filename = f"temp_cmd_{client_id.replace(':', '_')}_{timestamp}.wav"
            sample_rate = header.get('sample_rate', 16000)
            channels = header.get('channels', 1)
            
            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data)
            
            # 1. ASR识别
            print(f"[{client_id}][{request_id[:8]}]  Running ASR...")
            asr_start = time.time()
            text = controller.recognize_speech(filename)
            text = normalize(text)
            asr_time = time.time() - asr_start
            
            if not text or not text.strip():
                print(f"[{client_id}][{request_id[:8]}]  ASR failed or empty")
                self.send_response(client_socket, 'ERROR', 'ASR recognition failed or empty result', request_id)
                return
            
            print(f"[{client_id}][{request_id[:8]}]  ASR Result: '{text}' ({asr_time:.2f}s)")
            
            # 立即发送ASR结果
            self.send_response(client_socket, 'ASR_RESULT', {
                'text': text,
                'asr_time': round(asr_time, 2)
            }, request_id)
            
            # 2. LLM处理
            print(f"[{client_id}][{request_id[:8]}]  Processing with LLM...")
            llm_start = time.time()
            
            # 确保使用UTF-8编码传递中文
            content = controller.bot.chat(text)
            
            llm_time = time.time() - llm_start
            
            print(f"[{client_id}][{request_id[:8]}]  LLM Response ({llm_time:.2f}s):")
            print(f"   {content[:200]}...")  # 打印前200字符
            
            # 重置对话上下文
            controller.bot.chat("reset")
            
            # 3. 解析并执行命令
            command = controller.parse_response(content)
            
            if command:
                print(f"[{client_id}][{request_id[:8]}]  Executing: {command}")
                try:
                    controller.execute_commands(command)
                    execution_status = "success"
                except Exception as e:
                    print(f"[{client_id}][{request_id[:8]}]  Execution error: {e}")
                    execution_status = f"error: {str(e)}"
                
                self.send_response(client_socket, 'SUCCESS', {
                    'text': text,
                    'response': content,
                    'command': command,
                    'execution_status': execution_status,
                    'asr_time': round(asr_time, 2),
                    'llm_time': round(llm_time, 2),
                    'total_time': round(asr_time + llm_time, 2)
                }, request_id)
            else:
                print(f"[{client_id}][{request_id[:8]}] ℹ No executable command")
                self.send_response(client_socket, 'INFO', {
                    'text': text,
                    'response': content,
                    'message': 'No executable command found in response',
                    'asr_time': round(asr_time, 2),
                    'llm_time': round(llm_time, 2)
                }, request_id)
        
        except Exception as e:
            print(f"[{client_id}][{request_id[:8]}]  Processing error: {e}")
            import traceback
            traceback.print_exc()
            self.send_response(client_socket, 'ERROR', str(e), request_id)
    
    def send_response(self, client_socket, msg_type, data, request_id=None):
        """发送响应给客户端"""
        try:
            response = {
                'type': msg_type,
                'data': data,
                'request_id': request_id,
                'timestamp': time.time()
            }
            response_json = json.dumps(response, ensure_ascii=False).encode('utf-8')
            
            # 发送响应长度 + 响应内容
            size = len(response_json).to_bytes(4, 'big')
            client_socket.sendall(size + response_json)
            
            print(f"    Sent {msg_type} response (ID: {request_id[:8] if request_id else 'N/A'})")
        except Exception as e:
            print(f"    Error sending response: {e}")

if __name__ == "__main__":
    server = LightweightVoiceServer(host='0.0.0.0', port=9999)
    server.start()