
import math

class PracticeSession:
    """
    Manages a practice session, tracking hits, misses, and scoring.
    """
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.combo = 0
        self.max_combo = 0
        self.score = 0
        self.total_notes = 0
        self.active = False
        
        # Scoring constants
        self.POINTS_PER_HIT = 100
        self.COMBO_MULTIPLIER_step = 10 # Increase multiplier every 10 hits
        
    def start(self, total_notes: int):
        """Start a new session."""
        self.active = True
        self.hits = 0
        self.misses = 0
        self.combo = 0
        self.max_combo = 0
        self.score = 0
        self.total_notes = total_notes
        print(f"[PracticeSession] Started. Total eligible notes: {self.total_notes}")
        
    def stop(self):
        """Stop current session."""
        self.active = False
        print(f"[PracticeSession] Stopped. Score: {self.score}, Hits: {self.hits}/{self.total_notes}")
        
    def register_hit(self, note_id: int, time_offset: float = 0):
        """
        Register a successful hit. 
        Calculates score based on combo.
        """
        if not self.active: return
        
        self.hits += 1
        self.combo += 1
        if self.combo > self.max_combo:
            self.max_combo = self.combo
            
        # Calculate multiplier (1x, 2x, 4x, 8x based on combo)
        multiplier = min(8, 2 ** (self.combo // 10))
        
        points = self.POINTS_PER_HIT * multiplier
        self.score += points
        
        return {
            'type': 'hit',
            'combo': self.combo,
            'score': self.score,
            'points': points
        }
        
    def register_miss(self):
        """Register a miss (break combo)."""
        if not self.active: return
        
        self.misses += 1
        self.combo = 0
        
        return {
            'type': 'miss',
            'combo': 0,
            'score': self.score
        }

    def get_summary(self):
        """Return session statistics."""
        accuracy = (self.hits / self.total_notes * 100) if self.total_notes > 0 else 0
        return {
            'score': self.score,
            'hits': self.hits,
            'misses': self.misses,
            'max_combo': self.max_combo,
            'accuracy': accuracy
        }
