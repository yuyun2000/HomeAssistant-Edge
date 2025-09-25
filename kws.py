#!/usr/bin/env python3

import sys
from pathlib import Path
import numpy as np

try:
    import sounddevice as sd
except ImportError:
    print("Please install sounddevice first. You can use")
    print()
    print("  pip install sounddevice")
    print()
    print("to install it")
    sys.exit(-1)

import sherpa_onnx


class KeywordSpotter:
    def __init__(
        self,
        tokens="./sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01/tokens.txt",
        encoder="./sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01/encoder-epoch-12-avg-2-chunk-16-left-64.int8.ort",
        decoder="./sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01/decoder-epoch-12-avg-2-chunk-16-left-64.ort",
        joiner="./sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01/joiner-epoch-12-avg-2-chunk-16-left-64.int8.ort",
        keywords_file="./sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01/keywords.txt",
        num_threads=1,
        provider="cpu",
        max_active_paths=4,
        num_trailing_blanks=1,
        keywords_score=1.0,
        keywords_threshold=0.25,
        sample_rate=16000,
    ):
        """
        初始化关键词检测器
        
        Args:
            tokens: tokens.txt 文件路径
            encoder: encoder 模型文件路径
            decoder: decoder 模型文件路径
            joiner: joiner 模型文件路径
            keywords_file: 关键词文件路径
            num_threads: 线程数
            provider: 运行设备 (cpu, cuda, coreml)
            max_active_paths: 解码时保持的活跃路径数
            num_trailing_blanks: 关键词后跟随的空白数量
            keywords_score: 关键词分数
            keywords_threshold: 触发阈值
            sample_rate: 音频采样率
        """
        
        # 检查文件是否存在
        self._assert_file_exists(tokens)
        self._assert_file_exists(encoder)
        self._assert_file_exists(decoder)
        self._assert_file_exists(joiner)
        self._assert_file_exists(keywords_file)

        # 初始化参数
        self.sample_rate = sample_rate
        self.stream = None
        
        # 创建 KeywordSpotter 实例
        self.kws = sherpa_onnx.KeywordSpotter(
            tokens=tokens,
            encoder=encoder,
            decoder=decoder,
            joiner=joiner,
            num_threads=num_threads,
            max_active_paths=max_active_paths,
            keywords_file=keywords_file,
            keywords_score=keywords_score,
            keywords_threshold=keywords_threshold,
            num_trailing_blanks=num_trailing_blanks,
            provider=provider,
        )
        
        # 创建流
        self.stream = self.kws.create_stream()

    def _assert_file_exists(self, filename: str):
        """检查文件是否存在"""
        assert Path(filename).is_file(), (
            f"{filename} does not exist!\n"
            "Please refer to "
            "https://k2-fsa.github.io/sherpa/onnx/kws/pretrained_models/index.html to download it"
        )

    def process_audio(self, audio_data):
        """
        处理音频数据，检测关键词
        
        Args:
            audio_data: 音频数据，numpy数组，采样率应为16kHz，单声道，float32类型
            
        Returns:
            str or None: 检测到的关键词，如果没有检测到则返回None
        """
        if self.stream is None:
            self.stream = self.kws.create_stream()
            
        # 接受音频数据
        self.stream.accept_waveform(self.sample_rate, audio_data.astype(np.float32))
        
        # 解码
        while self.kws.is_ready(self.stream):
            self.kws.decode_stream(self.stream)
            result = self.kws.get_result(self.stream)
            if result:
                # 检测到关键词后重置流
                self.kws.reset_stream(self.stream)
                return result
                
        return None

    def reset(self):
        """重置检测器状态"""
        if self.stream is not None:
            self.kws.reset_stream(self.stream)


    def close(self):
        """关闭检测器"""
        self.stream = None


def main():
    """主函数：使用麦克风实时检测关键词"""
    
    # 创建关键词检测器实例
    try:
        spotter = KeywordSpotter()
        print("Keyword spotter initialized successfully!")
    except Exception as e:
        print(f"Failed to initialize keyword spotter: {e}")
        return

    # 检查麦克风设备
    devices = sd.query_devices()
    if len(devices) == 0:
        print("No microphone devices found")
        return

    print("Available audio devices:")
    print(devices)
    default_input_device_idx = sd.default.device[0]
    print(f'Using default device: {devices[default_input_device_idx]["name"]}')

    print("\nStarted! Please speak (Press Ctrl+C to exit)")
    
    # 音频参数
    sample_rate = 16000
    samples_per_read = int(0.1 * sample_rate)  # 0.1 second = 100 ms
    detection_count = 0

    try:
        # 打开音频输入流
        with sd.InputStream(channels=1, dtype="float32", samplerate=sample_rate) as stream:
            while True:
                # 读取音频数据
                samples, _ = stream.read(samples_per_read)  # blocking read
                samples = samples.reshape(-1)
                
                # 处理音频数据
                keyword = spotter.process_audio(samples)
                
                # 如果检测到关键词
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