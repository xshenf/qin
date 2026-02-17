
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
        """Simple autocorrelation/FFT fallback"""
        # Simple HPS (Harmonic Product Spectrum) or YIN implementation could go here
        # For now, reuse the MainWindow's simple FFT approach logic or similar
        
        # FFT Peak
        if len(audio) < 2048:
            padded = np.zeros(2048)
            padded[:len(audio)] = audio
            audio = padded
            
        fft = np.fft.rfft(audio * np.hanning(len(audio)))
        magnitude = np.abs(fft)
        freqs = np.fft.rfftfreq(len(audio), 1.0 / self.sample_rate)
        
        peak_idx = np.argmax(magnitude)
        freq = freqs[peak_idx]
        
        # Simple confidence: peak vs mean
        confidence = magnitude[peak_idx] / (np.mean(magnitude) + 1e-6)
        confidence = min(1.0, confidence / 100.0) # Arbitrary scaling
        
        return float(freq), float(confidence)
