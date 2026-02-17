
import numpy as np
import scipy.signal

class AudioPreprocessor:
    """音频预处理模块
    
    负责将原始 PCM 音频数据转换为适合 MIR 算法（如音高检测、起始点检测）处理的格式。
    包含：
    1. DC 偏移移除
    2. 预加重 (Pre-emphasis)
    3. 能量门限 (Silence Gating)
    4. 加窗 (Windowing)
    5. 降采样 (Downsampling) - 可选
    """

    def __init__(self, sample_rate: int = 44100, target_sr: int = 22050):
        self.sample_rate = sample_rate
        self.target_sr = target_sr
        self.downsample_factor = sample_rate // target_sr
        
        # 预加重系数 (0.95 ~ 0.97)
        self.preemph_coeff = 0.97
        
        # 能量门限 (dB)
        self.silence_threshold_db = -60.0

    def process(self, audio: np.ndarray, apply_window: bool = True) -> np.ndarray:
        """执行完整预处理流程
        
        Args:
            audio: 输入音频帧 (float32)
            apply_window: 是否加窗 (Hanning)
            
        Returns:
            处理后的音频帧
        """
        if len(audio) == 0:
            return audio

        # 1. 移除 DC 偏移
        processed = audio - np.mean(audio)
        
        # 2. 预加重 (High-pass filter)
        # y[n] = x[n] - alpha * x[n-1]
        processed = np.append(processed[0], processed[1:] - self.preemph_coeff * processed[:-1])
        
        # 3. 降采样 (简单的切片抽取，生产环境可用 decimate)
        if self.downsample_factor > 1:
            processed = processed[::self.downsample_factor]
        
        # 4. 加窗
        if apply_window:
            window = np.hanning(len(processed))
            processed = processed * window
            
        return processed

    def get_energy_db(self, audio: np.ndarray) -> float:
        """计算音频段的 RMS 能量 (dB)"""
        rms = np.sqrt(np.mean(audio**2))
        if rms < 1e-10:
            return -100.0
        return 20 * np.log10(rms)

    def is_silence(self, audio: np.ndarray) -> bool:
        """判断是否静音"""
        return self.get_energy_db(audio) < self.silence_threshold_db
