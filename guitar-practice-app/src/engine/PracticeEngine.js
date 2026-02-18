import AudioEngine from '../audio/AudioEngine';

class PracticeEngine {
    constructor() {
        this.scoreApi = null;
        this.isPracticeRunning = false;
        this.noteStatus = new Map(); // noteId -> 'hit' | 'miss' | 'wrong'
        this.onNoteResult = null; // Callback for UI updates
        this.lastHitTime = 0;
        this.expectedNotes = [];

        // 音符稳定器：过滤瞬态噪声和泛音伪影
        this.noteStabilizer = new Map(); // noteName -> { count, lastFrame, data }
        this.frameCounter = 0;
        this.STABILITY_THRESHOLD = 2; // 2帧确认即显示 (~33ms at 60fps)
        this.DECAY_FRAMES = 4; // 消失4帧后移除 (~66ms)
        this.MAX_DISPLAY_NOTES = 3; // 最多同时显示3个音符
    }

    // Connect to Score components
    attachScore(scoreApi) {
        // If re-attaching same score, do nothing? Or should we allow update?
        if (this.scoreApi === scoreApi) return;

        this.scoreApi = scoreApi;
    }

    // Start practice loop
    start() {
        if (this.isPracticeRunning) return; // Prevent double start
        this.isPracticeRunning = true;
        this.noteStatus.clear(); // Clear previous session status
        this.noteStabilizer.clear(); // Clear stabilizer
        this.frameCounter = 0;
        this.loop();
    }

    setResultCallback(callback) {
        this.onNoteResult = callback;
    }

    setPitchCallback(callback) {
        this.onPitchUpdate = callback;
    }

    loop() {
        if (!this.isPracticeRunning) return;

        try {
            // YIN 算法：准确找基频（用于乐谱匹配）
            const pitchData = AudioEngine.getPitch();

            // FFT 多音检测：用于 UI 显示（允许泛音）
            const polyPitchData = AudioEngine.getPolyphonicPitch();

            // 通知 UI (PerformanceBar)
            if (this.onPitchUpdate) {
                // 轻量稳定化：2帧确认，过滤单帧毛刺
                this.frameCounter++;
                let rawNotes = polyPitchData.length > 0 ? polyPitchData : (pitchData ? [pitchData] : []);

                for (const note of rawNotes) {
                    const existing = this.noteStabilizer.get(note.note);
                    if (existing) {
                        existing.count++;
                        existing.lastFrame = this.frameCounter;
                        existing.data = note;
                    } else {
                        this.noteStabilizer.set(note.note, {
                            count: 1, lastFrame: this.frameCounter, data: note
                        });
                    }
                }

                // 清理过期音符
                for (const [name, info] of this.noteStabilizer) {
                    if (this.frameCounter - info.lastFrame > this.DECAY_FRAMES) {
                        this.noteStabilizer.delete(name);
                    }
                }

                // 输出稳定音符（2帧即显示）
                const stableNotes = [];
                for (const [, info] of this.noteStabilizer) {
                    if (info.count >= this.STABILITY_THRESHOLD) {
                        stableNotes.push(info.data);
                    }
                }
                stableNotes.sort((a, b) => (b.magnitude || 0) - (a.magnitude || 0));
                this.onPitchUpdate(stableNotes.slice(0, this.MAX_DISPLAY_NOTES));
            }

            // 2. Get current cursor position in ticks (only if score is loaded)
            if (this.scoreApi) {
                const currentTick = this.scoreApi.tickPosition;

                // 3. Find expected notes around this time
                // AlphaTab doesn't expose a simple "getNoteAtTick" for performance, 
                // we usually rely on 'playedBeatChanged' or pre-processing. 
                // For now, let's assume we have access to active notes via API or we scan.
                // A better approach for real-time is checking if any note is "active" (within duration)

                // Simplified: Check if pitch matches any note in the currently highlighted beats
                // This requires ScoreViewer to expose active notes or we access via scoreApi.

                // Since accessing AlphaTab model in real-time loop might be heavy, 
                // we can let ScoreViewer push "active notes" to us, OR we access a cached map.

                // For prototype: we will let ScoreViewer handle the "what note is it" 
                // and we just compare pitch here? No, PracticeEngine should drive logic.

                // Let's rely on `this.expectedNotes` which we can update via events.

                if (pitchData && this.expectedNotes && this.expectedNotes.length > 0) {
                    const detectedFreq = pitchData.frequency;

                    // Check against all expected notes (polyphony support in future)
                    for (const note of this.expectedNotes) {
                        if (this.noteStatus.has(note.id)) continue; // Already processed

                        let midi = note.midi;
                        if (!midi) {
                            const tuning = this.getTuning(note.string);
                            if (tuning !== undefined && tuning !== null) {
                                midi = tuning + note.fret;
                            }
                        }

                        if (!midi) continue;

                        // Calculate Note Frequency
                        // Freq = 440 * 2^((midi - 69) / 12)
                        const expectedFreq = 440 * Math.pow(2, (midi - 69) / 12);

                        // (Debug log removed - was causing severe performance degradation)

                        // Tolerance: +/- 0.6 semitone (approx 3.5% freq difference)
                        const diffRatio = detectedFreq / expectedFreq;
                        // 0.6 semitone ratio is approx 1.035
                        if (diffRatio > 0.965 && diffRatio < 1.035) {
                            // HIT!
                            this.handleNoteHit(note, currentTick);
                        }
                    }
                }
            } // end if (this.scoreApi)

        } catch (e) {
            console.error('PracticeEngine loop error:', e);
        }

        requestAnimationFrame(() => this.loop());
    }

    handleNoteHit(note, tick) {
        this.noteStatus.set(note.id, 'hit');
        // Analyze timing (tempo)
        let timing = 'perfect';
        if (tick < note.startTick - 960 / 4) timing = 'early'; // arbitrary threshold
        else if (tick > note.startTick + 960 / 4) timing = 'late';

        console.log(`Note Hit! ${note.result} Timing: ${timing}`);

        if (this.onNoteResult) {
            this.onNoteResult({
                type: 'hit',
                noteId: note.id,
                noteRef: note.ref,
                timing: timing
            });
        }
    }

    // Called by ScoreViewer when beat changes
    updateExpectedNotes(notes) {
        if (!this.isPracticeRunning) {
            this.expectedNotes = []; // Clear if not running to avoid stale checks
            return;
        }

        console.log("PracticeEngine: expected notes updated", notes.length);
        // Check for missed notes in previous beats
        if (this.expectedNotes && this.expectedNotes.length > 0) {
            this.expectedNotes.forEach(note => {
                const status = this.noteStatus.get(note.id);
                if (status !== 'hit') {
                    // MISS
                    this.noteStatus.set(note.id, 'miss');
                    console.log("PracticeEngine: Missed note", note.id);
                    if (this.onNoteResult) {
                        this.onNoteResult({
                            type: 'miss',
                            noteId: note.id,
                            noteRef: note.ref,
                            timing: 'late'
                        });
                    }
                }
            });
        }
        this.expectedNotes = notes;
    }

    getTuning(stringIndex) {
        if (!this.scoreApi || !this.scoreApi.score) return null;
        try {
            const track = this.scoreApi.score.tracks[0];
            const stave = track.staves[0];
            // Log tuning structure once
            if (Math.random() < 0.01) console.log("TuningObj:", stave.stringTuning);

            // AlphaTab 1.0+: stringTuning.tunings is the array of MIDI values
            return stave.stringTuning.tunings[stringIndex - 1]; // 0-based array, stringIndex is 1-based
        } catch (e) {
            console.warn("Could not get tuning", e);
            return null;
        }
    }
}

export default new PracticeEngine();
