
import numpy as np
import time
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.mir.alignment import ScoreFollower

def generate_sine_wave(freq, duration, sr=44100):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return 0.5 * np.sin(2 * np.pi * freq * t)

def main():
    print("[Simulation] Starting Canon in D Alignment Test...")
    
    # 1. Setup Score Data (Simulating Canon first few bars)
    # Canon in D Bass line usually: D - A - B - F# - G - D - G - A
    # Let's mock the events based on User logs which showed Note 62 (D4) and 50 (D3)
    # Event format: [start, dur, pitch, id]
    
    # Simulating a simple scale for testing: D4 (62) -> A3 (57) -> B3 (59) -> F#3 (54)
    # Each note 1.0 second
    events = [
        [0.0, 1.0, 62, 1], # D4  (293.66 Hz)
        [1.0, 1.0, 57, 2], # A3  (220.00 Hz)
        [2.0, 1.0, 59, 3], # B3  (246.94 Hz)
        [3.0, 1.0, 54, 4], # F#3 (185.00 Hz)
    ]
    
    follower = ScoreFollower()
    follower.load_score_from_midi_events(events)
    
    # 2. Generate Audio
    sr = 44100
    audio_segments = []
    
    # Silence start
    audio_segments.append(np.zeros(int(0.5 * sr)))
    
    # Notes (Perfect Pitch)
    audio_segments.append(generate_sine_wave(293.66, 1.0, sr)) # D4
    audio_segments.append(generate_sine_wave(220.00, 1.0, sr)) # A3
    audio_segments.append(generate_sine_wave(246.94, 1.0, sr)) # B3
    audio_segments.append(generate_sine_wave(185.00, 1.0, sr)) # F#3
    
    # Silence end
    audio_segments.append(np.zeros(int(1.0 * sr)))
    
    full_audio = np.concatenate(audio_segments)
    
    print(f"[Simulation] Generated Audio Length: {len(full_audio)/sr:.2f}s")
    
    # 3. Process Loops
    block_size = 1024 # ~23ms
    cursor = 0
    
    # We will simulate the "Real-time" loop provided by AudioIO
    # And feed it to ScoreFollower.process_frame
    
    detected_hits = 0
    total_checks = 0
    
    active_note_ids = set()
    
    print("\n[Simulation] Processing Frames...")
    
    sim_time = 0.0
    
    while cursor < len(full_audio):
        chunk = full_audio[cursor : cursor + block_size]
        if len(chunk) < block_size:
            chunk = np.pad(chunk, (0, block_size - len(chunk)))
            
        # Simulate Pitch Detection (Ideal)
        # We know what note 'should' be playing at sim_time
        # But here let's just cheat and say Freq is dominant freq of chunk
        # Or even better, use the follower's own chroma to check alignment
        
        # Simple FFT based F0 for logging
        fft = np.abs(np.fft.rfft(chunk * np.hanning(len(chunk))))
        freqs = np.fft.rfftfreq(len(chunk), 1/sr)
        peak_idx = np.argmax(fft)
        peak_freq = freqs[peak_idx]
        
        # Calculate RMS
        rms = np.sqrt(np.mean(chunk**2))
        conf = 1.0 if rms > 0.01 else 0.0
        
        if peak_freq < 50: peak_freq = 0 # Noise gate
        
        # Process Frame
        est_time = follower.process_frame(chunk, f0=peak_freq, confidence=conf)
        
        if cursor % (block_size * 10) == 0: # Print every ~200ms
             print(f"Time={sim_time:.2f}s | EstScoreTime={est_time:.2f}s | InputFreq={peak_freq:.1f}Hz")
        
        # Check Hits (Replicating MainWindow logic)
        active = follower.get_active_notes(est_time)
        if active:
            for n in active:
                nid = n['id']
                if nid in active_note_ids: continue
                
                # Check pitch diff
                import math
                target_freq = 440.0 * (2 ** ((n['pitch'] - 69) / 12.0))
                if peak_freq > 0:
                    err = abs(12 * math.log2(peak_freq / target_freq))
                    if err < 1.0: # Loose tolerance for sim
                        print(f"  >>> HIT! Note {n['pitch']} at {est_time:.2f}s (Err={err:.2f}semi)")
                        detected_hits += 1
                        active_note_ids.add(nid)
        
        cursor += block_size
        sim_time += block_size / sr
        
    print("\n[Simulation] Result:")
    print(f"Total Events: {len(events)}")
    print(f"Detected Hits: {detected_hits}")
    
    if detected_hits == len(events):
        print("PASS: All notes detected correctly.")
    else:
        print(f"FAIL: Missed {len(events) - detected_hits} notes.")

if __name__ == "__main__":
    main()
