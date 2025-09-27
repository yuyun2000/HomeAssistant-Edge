#!/usr/bin/env python3
import sys
from pathlib import Path
import numpy as np
import torch
import torchaudio
import torchaudio.compliance.kaldi as kaldi
import onnxruntime as ort
from collections import deque

try:
    import sounddevice as sd
except ImportError:
    print("Please install sounddevice first. You can use")
    print()
    print("  pip install sounddevice")
    print()
    sys.exit(-1)

class KeywordSpotter:
    def __init__(
        self,
        onnx_model="./himfive.onnx",
        feat_dim=80,
        sample_rate=16000,
        chunk_size=32,
        threshold=0.5,
        min_high_frames=3,
        window_size=80,
        min_interval_frames=200,
        provider="cpu",
    ):
        """
        初始化关键词检测器

        Args:
            onnx_model: ONNX 模型路径
            feat_dim: FBank 维度
            sample_rate: 音频采样率
            chunk_size: 推理块大小（帧数）
            threshold: 唤醒分数阈值
            min_high_frames: 窗口内需要的最少高分帧数
            window_size: 滑动窗口大小（帧）
            min_interval_frames: 两次唤醒最小间隔帧数
            provider: ONNX 运行设备 ("cpu", "cuda")
        """
        self.onnx_model = onnx_model
        self.feat_dim = feat_dim
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.threshold = threshold
        self.min_high_frames = min_high_frames
        self.window_size = window_size
        self.min_interval_frames = min_interval_frames

        # 加载模型
        self.ort_sess = ort.InferenceSession(onnx_model, providers=[provider.upper() + "ExecutionProvider"])

        # 初始化状态
        self.cache = np.zeros((1, 32, 88), dtype=np.float32)
        self.buffer = np.array([], dtype=np.float32)  # 存储未处理的音频数据
        self.scores = deque(maxlen=window_size * 2)    # 存储最近帧的分数
        self.frame_count = 0                           # 全局帧计数
        self.last_trigger_frame = -min_interval_frames # 上次触发帧索引

    def _compute_fbank(self, waveform):
        """计算 FBank 特征"""
        waveform_tensor = torch.from_numpy(waveform).unsqueeze(0) * (1 << 15)
        mat = kaldi.fbank(
            waveform_tensor,
            num_mel_bins=self.feat_dim,
            dither=0.0,
            energy_floor=0.0,
            sample_frequency=self.sample_rate
        )
        return mat.numpy()

    def process_audio(self, audio_data):
        """
        处理音频数据，检测关键词

        Args:
            audio_data: 音频数据，numpy数组，采样率应为16kHz，单声道，float32类型

        Returns:
            str or None: 检测到关键词时返回"唤醒词"，否则返回None
        """
        self.buffer = np.concatenate([self.buffer, audio_data])

        # 每次处理 chunk_size * 10ms 的数据
        frame_length = int(0.01 * self.sample_rate)  # 10ms per frame
        required_samples = self.chunk_size * frame_length

        while len(self.buffer) >= required_samples:
            # 提取 chunk 数据
            chunk_waveform = self.buffer[:required_samples]
            self.buffer = self.buffer[required_samples:]

            # 计算 FBank
            feats = self._compute_fbank(chunk_waveform)

            # 推理
            for i in range(0, feats.shape[0], self.chunk_size):
                feat_chunk = feats[i:i+self.chunk_size]
                if feat_chunk.shape[0] < self.chunk_size:
                    # 补零到 chunk_size
                    pad_len = self.chunk_size - feat_chunk.shape[0]
                    feat_chunk = np.pad(feat_chunk, ((0, pad_len), (0, 0)), mode='constant')

                feat_chunk = feat_chunk[np.newaxis, :, :]  # batch=1

                inputs = {
                    "input": feat_chunk.astype(np.float32),
                    "cache": self.cache
                }

                outputs = self.ort_sess.run(None, inputs)
                out_chunk, self.cache = outputs[0].flatten(), outputs[1]

                for score in out_chunk:
                    self.scores.append(score)
                    self.frame_count += 1

                    # 滑动窗口检测唤醒
                    if self.frame_count - self.last_trigger_frame < self.min_interval_frames:
                        continue

                    if len(self.scores) >= self.window_size:
                        recent_scores = list(self.scores)[-self.window_size:]
                        high_count = sum(s > self.threshold for s in recent_scores)
                        if high_count >= self.min_high_frames:
                            self.last_trigger_frame = self.frame_count
                            return "唤醒词"

        return None

    def reset(self):
        """重置检测器状态"""
        self.cache = np.zeros((1, 32, 88), dtype=np.float32)
        self.buffer = np.array([], dtype=np.float32)
        self.scores.clear()
        self.frame_count = 0
        self.last_trigger_frame = -self.min_interval_frames

    def close(self):
        """关闭检测器"""
        self.reset()

def main():
    """主函数：使用麦克风实时检测关键词"""
    try:
        spotter = KeywordSpotter()
        print("Keyword spotter initialized successfully!")
    except Exception as e:
        print(f"Failed to initialize keyword spotter: {e}")
        return

    devices = sd.query_devices()
    if len(devices) == 0:
        print("No microphone devices found")
        return

    print("Available audio devices:")
    print(devices)
    default_input_device_idx = sd.default.device[0]
    print(f'Using default device: {devices[default_input_device_idx]["name"]}')
    print("\nStarted! Please speak (Press Ctrl+C to exit)")

    sample_rate = 16000
    samples_per_read = int(0.1 * sample_rate)  # 0.1 second = 100 ms
    detection_count = 0

    try:
        with sd.InputStream(channels=1, dtype="float32", samplerate=sample_rate) as stream:
            while True:
                samples, _ = stream.read(samples_per_read)
                samples = samples.reshape(-1)

                keyword = spotter.process_audio(samples)

                if keyword:
                    print(f"[{detection_count}] Detected keyword: {keyword}")
                    detection_count += 1

    except KeyboardInterrupt:
        print("\nCaught Ctrl + C. Exiting")
    except Exception as e:
        print(f"\nError occurred: {e}")
    finally:
        spotter.close()
        print("Keyword spotter closed.")

if __name__ == "__main__":
    main()