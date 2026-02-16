"""
音频 I/O 模块 — 基于 PortAudio 的低延迟音频采集

使用 sounddevice 提供回调式音频输入，环形缓冲区存储最近音频数据，
供 MIR 引擎异步读取分析。
"""

import numpy as np
import sounddevice as sd
import threading
from typing import Optional, Callable


class RingBuffer:
    """无锁环形缓冲区，用于音频线程与分析线程之间的数据传递"""

    def __init__(self, capacity: int):
        """
        Args:
            capacity: 缓冲区容量（采样点数）
        """
        self.buffer = np.zeros(capacity, dtype=np.float32)
        self.capacity = capacity
        self.write_pos = 0
        self.available = 0  # 当前可读数据量

    def write(self, data: np.ndarray):
        """写入音频数据（音频回调线程调用）"""
        n = len(data)
        if n >= self.capacity:
            # 数据超过缓冲区大小，只保留最后 capacity 个样本
            self.buffer[:] = data[-self.capacity:]
            self.write_pos = 0
            self.available = self.capacity
            return

        # 写入位置回绕处理
        end = self.write_pos + n
        if end <= self.capacity:
            self.buffer[self.write_pos:end] = data
        else:
            first = self.capacity - self.write_pos
            self.buffer[self.write_pos:] = data[:first]
            self.buffer[:n - first] = data[first:]

        self.write_pos = end % self.capacity
        self.available = min(self.available + n, self.capacity)

    def read(self, n: int) -> Optional[np.ndarray]:
        """读取最近 n 个采样点（分析线程调用）

        Args:
            n: 需要读取的采样点数

        Returns:
            最近 n 个样本的副本，如果不足则返回 None
        """
        if self.available < n:
            return None

        read_start = (self.write_pos - n) % self.capacity
        if read_start + n <= self.capacity:
            return self.buffer[read_start:read_start + n].copy()
        else:
            first = self.capacity - read_start
            return np.concatenate([
                self.buffer[read_start:],
                self.buffer[:n - first]
            ]).copy()

    def read_latest(self, n: int) -> np.ndarray:
        """读取最近 n 个采样点，不足则补零"""
        result = self.read(n)
        if result is not None:
            return result
        # 可用数据不足，补零
        data = np.zeros(n, dtype=np.float32)
        if self.available > 0:
            actual = self.read(self.available)
            if actual is not None:
                data[-len(actual):] = actual
        return data


class AudioIO:
    """低延迟音频 I/O 管理器

    使用 PortAudio 后端（sounddevice），支持 ASIO、WASAPI、DirectSound。
    """

    def __init__(
        self,
        sample_rate: int = 44100,
        block_size: int = 256,
        buffer_seconds: float = 5.0,
        device: Optional[int] = None,
    ):
        """
        Args:
            sample_rate: 采样率（Hz）
            block_size: 每次回调的帧数（越小延迟越低）
                        256 @ 44100Hz ≈ 5.8ms
            buffer_seconds: 环形缓冲区长度（秒）
            device: 输入设备索引，None 为默认设备
        """
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.device = device
        self.ring_buffer = RingBuffer(int(sample_rate * buffer_seconds))
        self.stream: Optional[sd.InputStream] = None
        self.is_running = False

        # 回调钩子：每块音频到达时触发
        self.on_audio_block: Optional[Callable[[np.ndarray], None]] = None

        # 统计信息
        self.total_frames = 0
        self.overflows = 0

    def _audio_callback(self, indata, frames, time_info, status):
        """PortAudio 音频回调（在音频线程中运行）"""
        if status:
            if status.input_overflow:
                self.overflows += 1

        # 取第一通道（单声道）
        audio = indata[:, 0].astype(np.float32)
        self.ring_buffer.write(audio)
        self.total_frames += frames

        # 触发回调钩子
        if self.on_audio_block is not None:
            self.on_audio_block(audio)

    def start(self):
        """启动音频采集"""
        if self.is_running:
            return

        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            blocksize=self.block_size,
            device=self.device,
            channels=1,
            dtype='float32',
            callback=self._audio_callback,
            latency='low',
        )
        self.stream.start()
        self.is_running = True
        print(f"[AudioIO] 已启动: SR={self.sample_rate}, "
              f"BlockSize={self.block_size} "
              f"({self.block_size / self.sample_rate * 1000:.1f}ms), "
              f"Device={self.device or 'default'}")

    def stop(self):
        """停止音频采集"""
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.is_running = False
        print(f"[AudioIO] 已停止: 总帧数={self.total_frames}, 溢出={self.overflows}")

    def get_buffer(self, duration_ms: float = 50.0) -> np.ndarray:
        """获取最近一段音频数据

        Args:
            duration_ms: 需要的时长（毫秒）

        Returns:
            音频数据 numpy 数组
        """
        n_samples = int(self.sample_rate * duration_ms / 1000)
        return self.ring_buffer.read_latest(n_samples)

    def get_rms(self) -> float:
        """获取当前音频 RMS 电平"""
        block = self.ring_buffer.read_latest(self.block_size)
        return float(np.sqrt(np.mean(block ** 2)))

    def get_rms_db(self) -> float:
        """获取当前音频 RMS 电平（dB）"""
        rms = self.get_rms()
        if rms < 1e-10:
            return -100.0
        return 20 * np.log10(rms)

    @staticmethod
    def list_devices():
        """列出所有可用音频设备"""
        print(sd.query_devices())

    @staticmethod
    def get_default_device():
        """获取默认输入设备信息"""
        return sd.query_devices(kind='input')
