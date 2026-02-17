
import numpy as np
import warnings

# Try importing CREPE, handle if missing
try:
    import crepe
    HAS_CREPE = True
except ImportError:
    HAS_CREPE = False
    print("[PitchTracker] CREPE not found. Falling back to basic methods.")

class PitchTracker:
    """
    Pitch tracking wrapper supporting multiple algorithms.
    Default: CREPE (Convolutional Representation for Pitch Estimation) if available.
    """
    
    def __init__(self, sample_rate: int = 16000, model_capacity: str = 'tiny'):
        """
        Args:
            sample_rate: Audio sample rate (CREPE implies 16kHz usually)
            model_capacity: CREPE model size ('tiny', 'small', 'medium', 'large', 'full')
                            'tiny' is recommended for real-time CPU usage.
        """
        self.sample_rate = sample_rate
        self.model_capacity = model_capacity
        
    def predict(self, audio: np.ndarray) -> tuple[float, float]:
        """
        Predict pitch for a chunk of audio.
        
        Args:
            audio: 1D numpy array of audio samples (float32)
            
        Returns:
            (frequency, confidence)
            frequency: Detected pitch in Hz, or 0.0 if no pitch
            confidence: 0.0 to 1.0 confidence score
        """
        # Ensure correct shape/type for CREPE
        if len(audio) < 1024:
            return 0.0, 0.0
            
        if HAS_CREPE:
            # CREPE predict usually expects a batch or a long file.
            # For real-time frame-by-frame, we use `crepe.predict` on a single window.
            # Note: crepe.predict can be slow if not optimized or running on GPU.
            # For real-time, we might need a persistent model session or use 'tiny'.
            
            # Step size 10ms is standard
            try:
                # Suppress verbose TF/CREPE output
                # time, frequency, confidence, activation = ...
                # We pass verbose=0
                time, frequency, confidence, _ = crepe.predict(
                    audio, 
                    self.sample_rate, 
                    viterbi=True, 
                    step_size=len(audio)/self.sample_rate*1000, # Single step
                    model_capacity=self.model_capacity,
                    verbose=0
                )
                
                if len(frequency) > 0:
                    # Return the median or mean of the chunk if multiple frames detected
                    # Usually for a small buffer we get 1 or few frames
                    best_idx = np.argmax(confidence)
                    return float(frequency[best_idx]), float(confidence[best_idx])
            except Exception as e:
                print(f"[PitchTracker] CREPE error: {e}")
                return self._fallback_pitch(audio)
                
        return self._fallback_pitch(audio)

    def _fallback_pitch(self, audio: np.ndarray) -> tuple[float, float]:
        """Robust pitch detection using YIN algorithm or librosa"""
        try:
            import librosa
            # Expanded range to cover full guitar fretboard
            fmin = 50
            fmax = 1500
            
            # Use YIN
            pitches = librosa.yin(audio, fmin=fmin, fmax=fmax, sr=self.sample_rate, 
                                 frame_length=len(audio))
            
            # pitches is an array
            freq = float(np.median(pitches))
            
            # Improved Confidence Estimation
            # 1. Amplitude factor
            rms = np.sqrt(np.mean(audio**2))
            amp_conf = min(1.0, rms * 50) 
            
            # 2. Harmonicity factor
            # Check how well the periodicity matches (using auto-correlation peak)
            corr = np.correlate(audio, audio, mode='full')
            corr = corr[len(corr)//2:]
            if len(corr) > 1:
                max_corr = np.max(corr[1:])
                total_energy = corr[0] + 1e-10
                harm_conf = max_corr / total_energy
            else:
                harm_conf = 0.5
                
            conf = float(amp_conf * harm_conf)
            return freq, conf
        except (ImportError, Exception) as e:
            # print(f"[PitchTracker] Librosa YIN failed: {e}")
            return self._yin_custom(audio)

    def _yin_custom(self, audio: np.ndarray) -> tuple[float, float]:
        """Simplified YIN algorithm implementation"""
        # Parameters
        sr = self.sample_rate
        min_freq = 50
        max_freq = sr // 2
        tau_min = int(sr / max_freq)
        tau_max = int(sr / min_freq)
        
        # 1. Difference function
        # d[tau] = sum_{j=1..W} (x[j] - x[j+tau])^2
        window_size = len(audio) // 2
        difference = np.zeros(tau_max)
        for tau in range(1, tau_max):
            diff = audio[:window_size] - audio[tau:tau + window_size]
            difference[tau] = np.sum(diff ** 2)
            
        # 2. Cumulative Mean Normalized Difference Function (CMNDF)
        cmndf = np.zeros(tau_max)
        cmndf[0] = 1.0
        running_sum = 0.0
        for tau in range(1, tau_max):
            running_sum += difference[tau]
            if running_sum == 0:
                cmndf[tau] = 1.0
            else:
                cmndf[tau] = difference[tau] / (running_sum / tau)
                
        # 3. Absolute threshold
        threshold = 0.15
        tau_found = -1
        for tau in range(tau_min, tau_max):
            if cmndf[tau] < threshold:
                tau_found = tau
                # Find the local minimum after crossing threshold
                while tau + 1 < tau_max and cmndf[tau+1] < cmndf[tau]:
                    tau += 1
                    tau_found = tau
                break
        
        if tau_found == -1:
            # If no dip below threshold, take global minimum
            tau_found = np.argmin(cmndf[tau_min:]) + tau_min
            
        # Confidence calculation (depth of the dip)
        confidence = 1.0 - cmndf[tau_found]
        # Weight by volume
        rms = np.sqrt(np.mean(audio**2))
        confidence *= min(1.0, rms * 50)
        
        freq = sr / tau_found if tau_found > 0 else 0.0
        return float(freq), float(confidence)
