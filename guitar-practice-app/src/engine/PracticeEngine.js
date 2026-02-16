import AudioEngine from '../audio/AudioEngine';

class PracticeEngine {
    constructor() {
        this.scoreApi = null; // Reference to AlphaTab API
        this.isPracticeRunning = false;
        this.currentNote = null; // The note we expect the user to play
    }

    // Connect to Score components
    attachScore(scoreApi) {
        this.scoreApi = scoreApi;
    }

    // Start practice loop
    start() {
        if (!this.scoreApi) return;
        this.isPracticeRunning = true;
        this.loop();
    }

    stop() {
        this.isPracticeRunning = false;
    }

    loop() {
        if (!this.isPracticeRunning) return;

        // 1. Get current audio pitch
        const pitchData = AudioEngine.getPitch();

        if (pitchData) {
            console.log("Detected Pitch:", pitchData.note, pitchData.frequency);
            // TODO: Compare with this.scoreApi.player.tickPosition or similar
        }

        requestAnimationFrame(() => this.loop());
    }
}

export default new PracticeEngine();
