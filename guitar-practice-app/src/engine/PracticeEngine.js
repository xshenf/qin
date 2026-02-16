import AudioEngine from '../audio/AudioEngine';

class PracticeEngine {
    constructor() {
        this.scoreApi = null;
        this.isPracticeRunning = false;
        this.noteStatus = new Map(); // noteId -> 'hit' | 'miss' | 'wrong'
        this.onNoteResult = null; // Callback for UI updates
        this.lastHitTime = 0;
        this.expectedNotes = [];
    }

    // Connect to Score components
    attachScore(scoreApi) {
        this.scoreApi = scoreApi;
    }

    // Start practice loop
    start() {
        if (!this.scoreApi) return;
        this.isPracticeRunning = true;
        this.noteStatus.clear(); // Clear previous session status
        this.loop();
    }

    setResultCallback(callback) {
        this.onNoteResult = callback;
    }

    loop() {
        if (!this.isPracticeRunning) return;

        // 1. Get audio pitch
        const pitchData = AudioEngine.getPitch();

        // 2. Get current cursor position in ticks
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

                // Tolerance: +/- 0.6 semitone (approx 3.5% freq difference)
                const diffRatio = detectedFreq / expectedFreq;
                // 0.6 semitone ratio is approx 1.035
                if (diffRatio > 0.965 && diffRatio < 1.035) {
                    // HIT!
                    this.handleNoteHit(note, currentTick);
                }
            }
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
        // Check for missed notes in previous beats
        if (this.expectedNotes && this.expectedNotes.length > 0) {
            this.expectedNotes.forEach(note => {
                const status = this.noteStatus.get(note.id);
                if (status !== 'hit') {
                    // MISS
                    this.noteStatus.set(note.id, 'miss');
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
            // Assuming single track for now
            const track = this.scoreApi.score.tracks[0];
            const stave = track.staves[0];
            // AlphaTab string index is 1-based. Tuning array is 0-based.
            // string 1 is highest pitch? 
            // In AlphaTab, index 0 is usually highest string.
            // note.string is 1-based index (1=high E).
            return stave.stringTuning.tunings[stringIndex - 1];
        } catch (e) {
            console.warn("Could not get tuning", e);
            return null;
        }
    }
}

export default new PracticeEngine();
