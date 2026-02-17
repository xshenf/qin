
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
        
        # 预加重系数
        self.preemph_coeff = 0.97
        
        # 能量门限 (dB)
        self.silence_threshold_db = -60.0

        # 噪声型 (Noise Profile) 用于降噪
        self.noise_profile = None

    def set_noise_profile(self, audio_chunk: np.ndarray):
        """记录一段纯噪声作为指纹"""
        if len(audio_chunk) == 0:
            return
        # 移除 DC 并降采样以匹配处理流程
        processed = audio_chunk - np.mean(audio_chunk)
        if self.downsample_factor > 1:
            processed = processed[::self.downsample_factor]
        self.noise_profile = processed
        print(f"[Preprocessor] 已更新噪声型，长度: {len(self.noise_profile)}")

    def process(self, audio: np.ndarray, apply_window: bool = True, apply_preemph: bool = True, apply_denoise: bool = True) -> np.ndarray:
        """执行预处理流程
        
        Args:
            audio: 输入音频帧
            apply_window: 是否加窗
            apply_preemph: 是否应用预加重 (音高检测建议关闭)
            apply_denoise: 是否执行降噪
        """
        if len(audio) == 0:
            return audio

        # 1. 移除 DC 偏移
        processed = audio - np.mean(audio)
        
        # 2. 降噪 (Noise Reduction)
        if apply_denoise and self.noise_profile is not None:
            processed = self._reduce_noise(processed)

        # 3. 预加重 (High-pass)
        if apply_preemph:
            processed = np.append(processed[0], processed[1:] - self.preemph_coeff * processed[:-1])
        
        # 4. 降采样
        if self.downsample_factor > 1:
            processed = processed[::self.downsample_factor]
        
        # 5. 加窗
        if apply_window:
            window = np.hanning(len(processed))
            processed = processed * window
            
        return processed

    def _reduce_noise(self, audio: np.ndarray) -> np.ndarray:
        """执行降噪处理"""
        try:
            import noisereduce as nr
            # noisereduce 效果通常很好
            return nr.reduce_noise(y=audio, sr=self.target_sr, stationary=True, 
                                   y_noise=self.noise_profile)
        except ImportError:
            # 简单谱减法 (Spectral Subtraction) 简化版
            # 仅在没有 noisereduce 时使用
            return audio # Placeholder or simple implementation

    def get_energy_db(self, audio: np.ndarray) -> float:
        """计算音频段的 RMS 能量 (dB)"""
        rms = np.sqrt(np.mean(audio**2))
        if rms < 1e-10:
            return -100.0
        return 20 * np.log10(rms)

    def is_silence(self, audio: np.ndarray) -> bool:
        """判断是否静音"""
        return self.get_energy_db(audio) < self.silence_threshold_db
