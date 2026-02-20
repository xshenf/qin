import AudioEngine from '../audio/AudioEngine';

class PracticeEngine {
    constructor() {
        this.scoreApi = null;
        this.isPracticeRunning = false;
        this.noteStatus = new Map(); // noteId -> 'hit' | 'miss' | 'wrong'
        this.onNoteResult = null; // Callback for UI updates
        this.lastHitTime = 0;
        this.expectedNotes = [];
        this.isFollowMode = false;

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

    stop() {
        this.isPracticeRunning = false;
        this.expectedNotes = [];
    }

    setFollowMode(active) {
        this.isFollowMode = active;
        console.log("PracticeEngine Follow Mode:", active);
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

                // Combine YIN and FFT peaks for comprehensive matching
                let pitchesToCheck = [];
                if (pitchData) pitchesToCheck.push(pitchData);
                if (polyPitchData && polyPitchData.length > 0) {
                    pitchesToCheck.push(...polyPitchData);
                }

                if (pitchesToCheck.length > 0 && this.expectedNotes && this.expectedNotes.length > 0) {
                    const isLoudAttack = pitchData && pitchData.isAttack;

                    // Check against all expected notes
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

                        let matched = false;

                        if (this.isFollowMode) {
                            // In Follow Mode: 
                            // 1. Any clear new pluck (attack) triggers the beat progression immediately.
                            // 2. Or, if they let it ring and it configures matches within +/- 12 semitones
                            if (isLoudAttack) {
                                matched = true;
                            } else {
                                for (const p of pitchesToCheck) {
                                    const diffRatio = p.frequency / expectedFreq;
                                    if (diffRatio > 0.5 && diffRatio < 2.0) {
                                        matched = true;
                                        break;
                                    }
                                }
                            }
                        } else {
                            // In Practice Mode: Strict +/- 0.6 semitone tolerance
                            const minRatio = 0.965;
                            const maxRatio = 1.035;

                            for (const p of pitchesToCheck) {
                                const diffRatio = p.frequency / expectedFreq;

                                // Direct match
                                if (diffRatio > minRatio && diffRatio < maxRatio) {
                                    matched = true; break;
                                }
                                // Harmonic tolerance: Allow octave higher (common guitar artifact)
                                if (diffRatio > (minRatio * 2) && diffRatio < (maxRatio * 2)) {
                                    matched = true; break;
                                }
                                // Harmonic tolerance: Allow octave lower ("missing fundamental" phenomenon)
                                if (diffRatio > (minRatio * 0.5) && diffRatio < (maxRatio * 0.5)) {
                                    matched = true; break;
                                }
                            }
                        }

                        if (matched) {
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

        // Follow Mode Logic: If all notes in current beat are hit, advance tick
        if (this.isFollowMode && this.scoreApi && this.expectedNotes.length > 0) {
            const allHit = this.expectedNotes.every(n => this.noteStatus.get(n.id) === 'hit');
            if (allHit) {
                // Calculate next beat tick (start + duration of the current beat notes)
                // We use a small epsilon offset to ensure we step into the NEXT beat properly
                const beatEndTick = this.expectedNotes[0].startTick + this.expectedNotes[0].duration;
                console.log(`%c[FOLLOW MODE] ✅ 匹配成功！自动推进光标到 Tick: ${beatEndTick}`, 'color: #3498db; font-size: 14px; font-weight: bold;');

                // Set tick position (this updates the internal cursor)
                this.scoreApi.tickPosition = beatEndTick;

                // Force a player update/seek so the UI actually scrolls if out of bounds
                // Often 'tickPosition' assignment handles UI but in paused state it may not scroll.
                if (this.scoreApi.player && this.scoreApi.player.state === 0) { // 0 represents Paused/Stopped in most AlphaTab versions
                    // Trigger a mock play/pause or just force UI layout
                    // this.scoreApi.playPause(); setTimeout(() => this.scoreApi.playPause(), 10);
                }
            }
        }
    }

    // Called by ScoreViewer when beat changes
    updateExpectedNotes(notes) {
        if (!this.isPracticeRunning) {
            this.expectedNotes = []; // Clear if not running to avoid stale checks
            return;
        }

        // --- ADDED LOGGING FOR USER ---
        if (notes && notes.length > 0) {
            const beatId = notes[0].ref?.beat?.id || 'Unknown Beat';
            const measureStr = notes[0].ref?.beat?.voice?.bar?.index !== undefined
                ? (notes[0].ref.beat.voice.bar.index + 1) : '?';

            const noteNames = notes.map(n => {
                let midi = n.midi;
                if (!midi) {
                    const tuning = this.getTuning(n.string);
                    if (tuning !== null && tuning !== undefined) {
                        midi = tuning + n.fret;
                    }
                }
                const expectedFreq = midi ? (440 * Math.pow(2, (midi - 69) / 12)).toFixed(1) + 'Hz' : 'Unknown';
                return `[第${n.string}弦${n.fret}品 (${expectedFreq})]`;
            }).join(', ');

            console.log(`%c[FOLLOW MODE] 目标小节: 第${measureStr}小节, 节拍ID:${beatId}, 期望音符: ${noteNames}`, 'color: #42b883; font-weight: bold;');
        }
        // ------------------------------

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
