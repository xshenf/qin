# Guitar Pro - System Architecture & Design

## Goal Description
Develop a professional-grade guitar practice application that uses advanced Music Information Retrieval (MIR) technologies to provide real-time, accurate feedback and score following (audio-to-score alignment).

## Architecture Overview
The system follows a modular architecture separating Audio I/O, Signal Processing (MIR), and UI Rendering.

### High-Level Diagram
```mermaid
graph TD
    A[Guitar Input] --> B(AudioIO / PortAudio)
    B --> C{RingBuffer}
    C --> D[Preprocessor]
    D --> E[MIR Analysis Engine]
    
    E --> F[Pitch Detection]
    E --> G[Onset Detection]
    E --> H[Alignment / Score Following]
    
    I[Score Data (AlphaTab/GP)] --> H
    
    H --> J[Sync Engine]
    J --> K[ScoreView (UI)]
    F --> K
    
    K --> L[Visual Feedback]
```

## Core Modules

### 1. Audio Engine (`src.audio`)
- **IO**: `sounddevice` (PortAudio) via `AudioIO` class. Low-latency callback (<10ms).
- **Buffering**: Lock-free `RingBuffer` for thread-safe data transfer to implementation thread.
- **Preprocessing**: High-pass filter (pre-emphasis), Noise Gate, Windowing.

### 2. MIR Pipeline (`src.mir`)
State-of-the-art algorithms utilized:
- **Pitch Tracking**:
  - **Monophonic**: `CREPE` (Deep CNN based F0 estimation). SOTA for robust pitch tracking locally.
  - **Polyphonic**: `Basic Pitch` (Spotify's lightweight model) or `librosa` multipitch as fallback.
- **Onset Detection**:
  - `madmom` (CNNOnsetProcessor) or Spectral Flux for low-latency triggers.
- **Audio-to-Score Alignment (Score Following)**:
  - **Feature**: Chroma Vectors (12-bin pitch class profile).
  - **Algorithm**: **Online Dynamic Time Warping (OLTW)**.
  - **Process**: 
    1. Look-ahead synthesized chroma from Score.
    2. Real-time chroma from Audio.
    3. Calculate cost matrix and find optimal path to map current audio time -> score time.

### 3. Synchronization & Feedback (`src.engine`)
- **PracticeEngine**: 
  - Compares detected F0/Notes against expected Notes (from Score).
  - Tolerances: Pitch +/- 50 cents, Timing +/- 100ms.
  - **Scoring**: Generates accuracy score and "Hit/Miss" events.
- **Loop Control**: Auto-handling of repeats and loops based on alignment confidence.

## Implementation Plan

### Phase 1: Infrastructure (Current)
- [x] Basic Audio I/O
- [x] Waveform/Spectrum Viz
- [x] AlphaTab Score Loading

### Phase 2: MIR Alignment Implementation [DONE]
- [x] **Pitch Detection**: Integrated `PitchTracker` (CREPE/BasicPitch ready).
- [x] **Feature Extraction**: Real-time Chroma feature extraction implemented.
- [x] **Alignment Logic**: Online DTW (OLTW) algorithm implemented.
- [x] **Score Synthesis**: Extracting note events from AlphaTab to synthesize reference chroma.

### Phase 3: Feedback UI [DONE]
- [x] **Cursor Sync**: Real-time score cursor synchronization via `setCursorTime` bridge.
- [x] **Note Coloring**: Dynamic note coloring (Green/Red) based on pitch accuracy.
- [x] **Scoring Engine**: `PracticeSession` for real-time score and combo tracking.

## Proposed Changes
### `pyproject.toml`
Ensure `librosa`, `crepe`, `madmom` are locked to compatible versions.

### `src/mir/alignment.py` [NEW]
- `class ScoreFollower`: Implementation of OLTW.

### `src/mir/pitch.py` [NEW]
- `class PitchTracker`: Wrapper for CREPE/BasicPitch inference.

### `src/engine/practice.py` [NEW]
- `class PracticeSession`: Manages state (Playing, Recording, Scoring).
