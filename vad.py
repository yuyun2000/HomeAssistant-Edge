import numpy as np
import onnxruntime as ort
import sounddevice as sd

class SileroVAD:
    def __init__(self, model_path="./models/silero-vad.onnx", threshold=0.5, buffer_size=3, silence_threshold=0.3):
        self.session = ort.InferenceSession(model_path)
        self.state = np.zeros((2, 1, 128), dtype=np.float32)
        self.sample_rate = 16000
        self.window_size = 512
        self.threshold = threshold
        self.buffer_size = buffer_size  # 缓冲区大小
        self.silence_threshold = silence_threshold  # 静默阈值
        self.prob_buffer = []  # 概率缓冲区
    
    def __call__(self, audio_chunk):
        # 预处理
        if audio_chunk.dtype != np.float32:
            audio_chunk = audio_chunk.astype(np.float32)
        if np.max(np.abs(audio_chunk)) > 1:
            audio_chunk = audio_chunk / 32768.0
            
        # 推理
        inputs = {
            'input': audio_chunk.reshape(1, -1),
            'state': self.state,
            'sr': np.array([self.sample_rate], dtype=np.int64)
        }
        outputs = self.session.run(None, inputs)
        
        self.state = outputs[1]
        prob = float(outputs[0][0][0])
        
        # 添加概率到缓冲区
        self.prob_buffer.append(prob)
        if len(self.prob_buffer) > self.buffer_size:
            self.prob_buffer.pop(0)  # 移除最旧的概率
        
        # 计算缓冲区平均值
        if len(self.prob_buffer) > 0:
            avg_prob = sum(self.prob_buffer) / len(self.prob_buffer)
            return avg_prob > self.silence_threshold
        else:
            return prob > self.threshold

# 使用示例
def run_vad():
    vad = SileroVAD("./models/silero-vad.onnx")
    
    def audio_callback(indata, frames, time, status):
        audio = indata.flatten()
        is_speaking = vad(audio)
        print(f"\r{'说话中' if is_speaking else '静默'}", end="")
    
    with sd.InputStream(channels=1, samplerate=16000, 
                       blocksize=512, callback=audio_callback):
        print("开始检测，按Enter停止...")
        input()

if __name__ == "__main__":
    run_vad()
