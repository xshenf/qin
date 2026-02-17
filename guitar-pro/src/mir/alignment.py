
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
        This provides much cleaner features for DTW than raw FFT.
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
        self.dtw = OnlineDTW(features, radius=50) # Set radius
        self.is_ready = True
        print(f"[ScoreFollower] Reference loaded: {len(features)} frames")
        
    def load_score_from_midi_events(self, events: list):
        """
        Synthesize reference features from a list of note events.
        
        Args:
            events: List of (start_time, duration, midi_pitch, note_id)
        """
        if not events:
            return
            
        self.events = events # Store for feedback lookup
            
        # 1. Determine total duration
        # Event might have 3 or 4 elements now
        last_event = max(events, key=lambda x: x[0] + x[1])
        total_duration = last_event[0] + last_event[1]
        
        # 2. Create time grid (100ms hop size or similar)
        # We need to match the hop size used in process_frame's time estimation logic
        # In process_frame we assumed 10Hz (0.1s). Let's stick to that for now or make it configurable.
        fps = 10 
        n_frames = int(np.ceil(total_duration * fps)) + 1
        
        ref_features = np.zeros((n_frames, 12))
        
        # 3. Fill features
        for event in events:
            # Handle variable length tuple (backwards compatibility or new format)
            if len(event) >= 3:
                start, dur, pitch = event[0], event[1], event[2]
                
                start_frame = int(start * fps)
                end_frame = int((start + dur) * fps)
                chroma_idx = pitch % 12
                
                # Simple binary activation
                ref_features[start_frame:end_frame, chroma_idx] = 1.0
            
        # Normalize
        norm = np.linalg.norm(ref_features, axis=1, keepdims=True)
        ref_features = np.divide(ref_features, norm, out=np.zeros_like(ref_features), where=norm > 0)
        
        self.load_score_features(ref_features)

    def get_active_notes(self, time: float) -> list:
        """Get list of notes active at the given time."""
        if not hasattr(self, 'events'):
            return []
            
        active = []
        for event in self.events:
            # event: [start, dur, pitch, id]
            if len(event) >= 4:
                start, dur, pitch, note_id = event
                if start <= time <= start + dur:
                    active.append({'start': start, 'dur': dur, 'pitch': pitch, 'id': note_id})
        return active


    def reset(self):
        """Reset alignment state."""
        if self.dtw:
            self.dtw.reset()

    def process_frame(self, audio_frame: np.ndarray, f0: float = None, 
                      confidence: float = 0.0) -> float:
        """
        Process live audio frame and return estimated time in score (seconds).
        Optional: can take pre-detected f0 to use F0-based Chroma.
        """
        if not self.is_ready:
            return 0.0
            
        # 1. Extract Feature (Chroma)
        if f0 is not None and f0 > 0:
            # Use high-quality F0-based Chroma if available
            chroma = self.chroma_extractor.compute_from_f0(f0, confidence)
        else:
            # Fallback to FFT-based Chroma
            chroma = self.chroma_extractor.compute(audio_frame)
        
        # 2. DTW Step
        frame_idx = self.dtw.step(chroma)
        
        # 3. Convert frame index to time
        # Assuming reference features were sampled at 10Hz or similar
        estimated_time = frame_idx * 0.1 
        
        return estimated_time

