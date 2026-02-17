
import numpy as np

class OnlineDTW:
    """
    Online Dynamic Time Warping (OLTW) implementation for real-time score following.
    
    References:
    - Dixon, S. (2005). Live Tracking of Musical Performances using On-Line Time Warping.
    - Arzt, A. et al. (2008). Real-time Music Tracking using Dynamic Time Warping.
    """
    
    def __init__(self, reference_features: np.ndarray, radius: int = 50):
        """
        Args:
            reference_features: Feature matrix of the score (N_frames x N_features).
                                Usually Chroma vectors.
            radius: Search radius constraints for DTW (stiffness).
        """
        self.ref = reference_features
        self.N, self.D = self.ref.shape
        self.radius = 50
        
        # State
        self.current_position = 0  # Frame index in reference
        self.accumulated_cost = np.zeros(self.N) + np.inf
        self.accumulated_cost[0] = 0

    def reset(self):
        """Reset alignment state to beginning."""
        self.current_position = 0
        self.accumulated_cost = np.zeros(self.N) + np.inf
        self.accumulated_cost[0] = 0
        
    def step(self, live_feature: np.ndarray) -> int:
        """
        Process one frame of live audio feature.
        
        Args:
            live_feature: 1D array of shape (N_features,).
            
        Returns:
            Estimated current frame index in the reference.
        """
        # 1. Calculate local cost (Cosine distance or Euclidean)
        # Cosine distance: 1 - (u . v) / (|u| |v|)
        # Normalized chromas are usually good with cosine.
        # Here assuming normalized features: cost = 1 - dot product
        
        cost_vec = 1.0 - np.dot(self.ref, live_feature)
        
        # 2. Update accumulated cost (Forward path only for simple OLTW)
        # allowed transitions: (0,1), (1,1), (2,1) -> stays, moves 1, moves 2
        
        new_accumulated = np.zeros_like(self.accumulated_cost) + np.inf
        
        # Limit search window around current hypothesis to reduce CPU load
        start = max(0, self.current_position - self.radius)
        end = min(self.N, self.current_position + self.radius * 2)
        
        for i in range(start, end):
            # Predecessors: i, i-1, i-2
            prev_costs = []
            
            # (i, j-1) -> stay in same ref frame (horizontal) - penalized
            if i < len(self.accumulated_cost):
                prev_costs.append(self.accumulated_cost[i] + cost_vec[i] * 2) 
            
            # (i-1, j-1) -> diagonal (normal tempo)
            if i > 0:
                prev_costs.append(self.accumulated_cost[i-1] + cost_vec[i])
                
            # (i-2, j-1) -> double speed (skip frame)
            if i > 1:
                prev_costs.append(self.accumulated_cost[i-2] + cost_vec[i] * 1.5)
                
            if prev_costs:
                new_accumulated[i] = min(prev_costs)
                
        self.accumulated_cost = new_accumulated
        
        # 3. Find global minimum in the current window as the position estimate
        # We assume the performer doesn't jump wildly.
        # Estimates are usually smoothed.
        
        best_idx = np.argmin(self.accumulated_cost[start:end]) + start
        self.current_position = best_idx
        
        return best_idx

class ChromaExtractor:
    """
    Lightweight real-time Chroma feature extractor.
    """
    def __init__(self, sample_rate: int = 44100, n_fft: int = 2048):
        self.sr = sample_rate
        self.n_fft = n_fft
        self.n_chroma = 12
        
        # Pre-compute FFT bin to Chroma mapping
        self.fft_freqs = np.fft.rfftfreq(n_fft, 1.0 / sample_rate)
        self.chroma_filter = self._build_chroma_filter()
        
    def _build_chroma_filter(self) -> np.ndarray:
        """Builds a matrix to map FFT bins to Chroma bins (Simple Box Filter)"""
        n_bins = len(self.fft_freqs)
        chroma_filter = np.zeros((n_bins, self.n_chroma))
        
        for i, f in enumerate(self.fft_freqs):
            if f < 50: continue # Skip low freq noise
            
            # Map freq to midi note
            # m = 69 + 12 * log2(f / 440)
            if f > 0:
                midi = 69 + 12 * np.log2(f / 440.0)
                chroma_idx = int(round(midi)) % 12
                chroma_filter[i, chroma_idx] = 1.0
                
        # Normalize filter
        return chroma_filter

    def compute(self, audio: np.ndarray) -> np.ndarray:
        """Compute chroma vector for an audio frame."""
        # 0. Pre-emphasis (High-pass filter to boost harmonics/transients for Guitar)
        if len(audio) > 1:
            audio = np.append(audio[0], audio[1:] - 0.97 * audio[:-1])

        # 1. Windowing
        if len(audio) < self.n_fft:
            # Pad if too short
            padded = np.zeros(self.n_fft)
            padded[:len(audio)] = audio
            audio = padded
        else:
            audio = audio[:self.n_fft]
            
        windowed = audio * np.hanning(self.n_fft)
        
        # 2. FFT
        fft = np.abs(np.fft.rfft(windowed))
        
        # 3. Map to Chroma
        chroma = np.dot(fft, self.chroma_filter)
        
        # 4. Normalize (L2) for Cosine Distance
        norm = np.linalg.norm(chroma)
        if norm > 0:
            chroma /= norm
            
        return chroma

    def compute_from_f0(self, f0: float, confidence: float) -> np.ndarray:
        """
        Synthesize a clean chroma vector from a detected pitch.
        (Kept for legacy or specific single-note checks)
        """
        chroma = np.zeros(12)
        if f0 > 30 and confidence > 0.1:
            # MIDI = 69 + 12 * log2(f0 / 440)
            midi = 69 + 12 * np.log2(f0 / 440.0)
            chroma_idx = int(round(midi)) % 12
            # Use confidence to weight the activation
            chroma[chroma_idx] = confidence
            
        # Normalize
        norm = np.linalg.norm(chroma)
        if norm > 0:
            chroma /= norm
        return chroma

class ScoreFollower:
    """
    High-level wrapper for Audio-to-Score alignment.
    """
    def __init__(self, sample_rate: int = 44100):
        self.sr = sample_rate
        self.chroma_extractor = ChromaExtractor(sample_rate)
        self.dtw: OnlineDTW = None
        self.is_ready = False
        
    def load_score_features(self, features: np.ndarray):
        """
        Load reference features extracted from score (MIDI/AlphaTab).
        features: (N_time_steps, 12)
        """
        self.dtw = OnlineDTW(features, radius=100) # Set radius
        self.is_ready = True
        print(f"[ScoreFollower] Reference loaded: {len(features)} frames")
        
    def load_score_from_midi_events(self, events: list):
        """
        Synthesize reference features from a list of note events.
        [FINAL_STABILITY_V3] 2026-02-17
        """
        if not events:
            print("[ScoreFollower] ERROR: Received empty events list.")
            return

        print(f"[ScoreFollower] load_score_from_midi_events: Received {len(events)} events.")
        # DEBUG: Print raw samples to catch scaling bugs
        print(f"[ScoreFollower] RAW SAMPLE (First): {events[0]}")
        if len(events) > 1:
            print(f"[ScoreFollower] RAW SAMPLE (Second): {events[1]}")
        print(f"[ScoreFollower] RAW SAMPLE (Last): {events[-1]}")
        
        # 1. Filter and clean data
        valid_events = []
        for e in events:
            if e and len(e) >= 3:
                try:
                    start = float(e[0])
                    dur = float(e[1])
                    pitch = int(e[2])
                    note_id = int(e[3]) if len(e) > 3 else -1
                    
                    if not (np.isnan(start) or np.isnan(dur)):
                        valid_events.append([start, dur, pitch, note_id])
                except (TypeError, ValueError):
                    continue
        
        if not valid_events:
            print("[ScoreFollower] ERROR: No valid events to process after filtering.")
            return
            
        self.events = valid_events
        print(f"[ScoreFollower] Events loaded: {len(self.events)}")
            
        # 2. Determine total duration
        try:
            # Sort by end time to find real duration
            max_end = 0
            for start, dur, *rest in valid_events:
                max_end = max(max_end, start + dur)
            
            total_duration = max_end
            print(f"[ScoreFollower] LOGICAL DURATION: {total_duration:.2f} seconds.")
            
            if total_duration < 1.0 and len(valid_events) > 10:
                print("[ScoreFollower] WARNING: Duration is extremely short. Check JS time units!")
        except Exception as e:
            print(f"[ScoreFollower] Exception in duration calculation: {e}")
            total_duration = 0
            
        if total_duration <= 0:
            print("[ScoreFollower] ABORT: Total duration is 0.")
            return
        
        # 3. Create time grid (10Hz)
        fps = 10 
        n_frames = int(np.ceil(total_duration * fps)) + 5 # Safety buffer
        print(f"[ScoreFollower] Initializing reference matrix: {n_frames} frames ({total_duration:.2f}s @ {fps}fps)")
        
        ref_features = np.zeros((n_frames, 12))
        
        # 4. Fill features
        for start, dur, pitch, *rest in valid_events:
            start_frame = int(round(start * fps))
            end_frame = int(round((start + dur) * fps))
            chroma_idx = int(pitch % 12)
            
            if 0 <= start_frame < n_frames:
                ref_features[start_frame:min(end_frame + 1, n_frames), chroma_idx] = 1.0
                
        # 5. Load features into DTW
        self.load_score_features(ref_features)
            
        # Normalize for Cosine distance
        norm = np.linalg.norm(ref_features, axis=1, keepdims=True)
        ref_features = np.divide(ref_features, norm, out=np.zeros_like(ref_features), where=norm > 0)
        
        self.load_score_features(ref_features)

    def get_active_notes(self, time: float) -> list:
        """Get list of notes active at the given time (in seconds)."""
        if not hasattr(self, 'events'):
            return []
            
        active = []
        for event in self.events:
            # event: [startTime, duration, midiPitch, noteId]
            if len(event) >= 4:
                start, dur, pitch, note_id = event[:4]
                # Allow a small 0.1s tolerance
                if (start - 0.1) <= time <= (start + dur + 0.1):
                    active.append({'start': start, 'dur': dur, 'pitch': pitch, 'id': note_id})
        
        # DEBUG: If no notes found but we are within total duration, maybe print?
        # limiting print to avoid spam, handled in MainWindow
                    
        return active

    def reset(self):
        """Reset alignment state."""
        if self.dtw:
            self.dtw.reset()

    def process_frame(self, audio_frame: np.ndarray, f0: float = None, 
                      confidence: float = 0.0) -> tuple[float, np.ndarray]:
        """
        Process live audio frame.
        Returns: (estimated_time, chroma_vector)
        """
        if not self.is_ready:
            return 0.0, np.zeros(12)
            
        # 1. Extract Feature (Always use Full Spectrum Chroma for Polyphony)
        # Even if we have F0, we want the full harmonic context for chords.
        chroma = self.chroma_extractor.compute(audio_frame)
        
        # 2. DTW Step
        frame_idx = self.dtw.step(chroma)
        
        # 3. Convert frame index to time
        # Assuming reference features were sampled at 10Hz or similar
        estimated_time = frame_idx * 0.1 
        
        return estimated_time, chroma

    def check_chroma_hit(self, chroma: np.ndarray, target_pitch: int, threshold: float = 0.6) -> bool:
        """
        Check if the target pitch is present in the chroma vector (Spectral Energy Check).
        STRICTER VERSION:
        1. Checks if chroma has enough variance (rejects flat noise).
        2. Checks if target bin is significant.
        """
        if chroma is None or len(chroma) != 12:
            return False
            
        # 1. Reject noise (flat spectrum or silence)
        # If max value is too low, it's silence/background noise
        if np.max(chroma) < 0.3:
            return False
            
        # 2. Reject percussive/atonal sounds (Low Peakiness)
        # A clear tone should have peaks. Flat chroma means noise.
        mean_val = np.mean(chroma) + 1e-6
        peakiness = np.max(chroma) / mean_val
        if peakiness < 2.5: # Heuristic: Uniform distribution gives ~1.0. Tonal needs > 2.5
            return False
            
        target_idx = target_pitch % 12
        energy = chroma[target_idx]
        
        # Check neighbors (leakage)
        left = chroma[(target_idx - 1) % 12]
        right = chroma[(target_idx + 1) % 12]
        
        # If primary bin is strong
        if energy > threshold:
            return True
            
        # If energy is spread to neighbors (tuning drift)
        if (left + energy + right) > (threshold * 1.5):
            return True
            
        return False
