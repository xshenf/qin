
import numpy as np
import librosa
import os

try:
    import onnxruntime as ort
    HAS_ONNX = True
except ImportError:
    HAS_ONNX = False

class RMVPE:
    """
    Robust Model for Vocal Pitch Estimation (RMVPE) implementation via ONNX.
    Optimized for real-time guitar pitch tracking.
    """
    def __init__(self, model_path: str = "vendor/models/rmvpe.onnx", device: str = "cpu"):
        self.model_path = model_path
        self.resample_sr = 16000
        self.n_fft = 2048
        self.hop_length = 320
        self.n_mels = 128
        self.fmin = 30.0
        self.fmax = 8000.0
        
        # Precompute frequency bins for F0 estimation
        # RMVPE uses 360 bins from 31.11Hz (C1) to 7902.13Hz (B8) with 20 cents step
        self.cent_table = 20.0 * np.arange(360) + 1200.0 * np.log2(31.1127 / 10.0)
        self.freq_table = 10.0 * (2.0 ** (self.cent_table / 1200.0))
        
        if HAS_ONNX and os.path.exists(model_path):
            providers = ['CPUExecutionProvider']
            if device == "gpu":
                providers = ['CUDAExecutionProvider'] + providers
            
            try:
                self.session = ort.InferenceSession(model_path, providers=providers)
                self.is_ready = True
                device_info = self.session.get_providers()[0]
                print(f"[RMVPE] 模型加载成功: {model_path} ({device_info})")
                
                # Warmup to avoid first-run lag (important for real-time)
                self._warmup()
            except Exception as e:
                print(f"[RMVPE] Failed to load ONNX model: {e}")
                self.is_ready = False
        else:
            self.is_ready = False
            if not HAS_ONNX:
                print("[RMVPE] onnxruntime not found.")
            elif not os.path.exists(model_path):
                print(f"[RMVPE] Model file not found at {model_path}")

    def _warmup(self):
        """Run fake inference to pre-warm the model and resampler."""
        try:
            # 1 second of silence at 16kHz
            dummy_audio = np.zeros(self.resample_sr, dtype=np.float32)
            self.predict(dummy_audio, self.resample_sr)
            print("[RMVPE] 模型预热完成")
        except Exception as e:
            print(f"[RMVPE] Warmup failed: {e}")

    def preprocess(self, audio: np.ndarray, sr: int) -> tuple[np.ndarray, int]:
        """
        Convert audio chunk to Mel spectrogram with RMVPE params.
        Returns: (mel_spectrogram, original_n_frames)
        """
        # 1. Resample to 16kHz if needed
        if sr != self.resample_sr:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=self.resample_sr)
        
        # 2. Compute Mel spectrogram
        # Ensure audio is at least n_fft long to avoid librosa warnings
        if len(audio) < self.n_fft:
            audio = np.pad(audio, (0, self.n_fft - len(audio)), mode='constant')
            
        mel = librosa.feature.melspectrogram(
            y=audio, 
            sr=self.resample_sr, 
            n_fft=self.n_fft, 
            hop_length=self.hop_length, 
            n_mels=self.n_mels,
            fmin=self.fmin,
            fmax=self.fmax
        )
        
        # 3. Log scale
        mel = librosa.power_to_db(mel, ref=np.max)
        
        # 4. Normalize
        mel = (mel + 80.0) / 80.0
        
        # 5. U-Net Padding: Axis 2 (time) must be multiple of 32
        # Error fix: concat axis dimensions mismatch
        n_frames = mel.shape[1]
        pad_size = (32 - (n_frames % 32)) % 32
        if pad_size > 0:
            mel = np.pad(mel, ((0, 0), (0, pad_size)), mode='constant')
            
        # 6. Format for ONNX: [batch, n_mels, n_frames]
        if mel.ndim == 2:
            mel = mel[np.newaxis, :, :]
            
        return mel.astype(np.float32), n_frames

    def predict(self, audio: np.ndarray, sr: int) -> tuple[float, float]:
        """
        Inference F0 and confidence.
        """
        if not self.is_ready:
            return 0.0, 0.0
            
        # 1. Preprocess
        mel, n_frames = self.preprocess(audio, sr)
        
        # 2. Run ONNX session
        input_name = self.session.get_inputs()[0].name
        outputs = self.session.run(None, {input_name: mel})
        
        # RMVPE output is [batch, n_frames_padded, 360] probs
        # 3. Crop back to original n_frames
        probs = outputs[0][0][:n_frames] # Take first batch and crop
        
        # 4. Post-process
        if len(probs) > 0:
            # Take middle frame of the chunk for real-time responsiveness
            best_frame_idx = len(probs) // 2
            frame_probs = probs[best_frame_idx]
            
            conf = float(np.max(frame_probs))
            if conf < 0.1: # Threshold
                return 0.0, conf
                
            # Gaussian blurring or center of mass for better precision
            idx = np.argmax(frame_probs)
            # Take a small window around peak
            start = max(0, idx - 4)
            end = min(360, idx + 5)
            weights = frame_probs[start:end]
            cents = self.cent_table[start:end]
            
            # Weighted average in cent space
            predicted_cent = np.sum(weights * cents) / np.sum(weights)
            f0 = 10.0 * (2.0 ** (predicted_cent / 1200.0))
            
            return float(f0), conf
            
        return 0.0, 0.0
