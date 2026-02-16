import { YIN } from 'pitchfinder';

class AudioEngine {
    constructor() {
        this.audioContext = null;
        this.mediaStream = null;
        this.analyser = null;
        this.detectPitch = null;
        this.buffer = null;
        this.isListening = false;
        
        // Configuration
        this.sampleRate = 44100;
        this.bufferSize = 2048; // Higher buffer size = better frequency resolution, more latency
    }

    async init() {
        if (!navigator.mediaDevices) {
            throw new Error("Microphone access is not supported in this browser.");
        }

        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.sampleRate = this.audioContext.sampleRate;
            
            // Initialize Pitchfinder algorithm (YIN is generally good for monophonic instruments like guitar single notes)
            this.detectPitch = YIN({ sampleRate: this.sampleRate });
            
            // Create analyser node
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = this.bufferSize;
            this.buffer = new Float32Array(this.analyser.fftSize);
            
            console.log("AudioEngine initialized. Sample Rate:", this.sampleRate);
        } catch (e) {
            console.error("AudioEngine initialization failed:", e);
            throw e;
        }
    }

    async startMicrophone() {
        if (!this.audioContext) await this.init();

        try {
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
            }

            // Request microphone access
            this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
            
            // Create source node from stream
            const source = this.audioContext.createMediaStreamSource(this.mediaStream);
            
            // Connect source to analyser (do NOT connect to destination to avoid feedback loop)
            source.connect(this.analyser);
            
            this.isListening = true;
            console.log("Microphone started.");
        } catch (e) {
            console.error("Failed to access microphone:", e);
            throw e;
        }
    }

    stopMicrophone() {
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
            this.mediaStream = null;
        }
        this.isListening = false;
        console.log("Microphone stopped.");
    }

    getPitch() {
        if (!this.isListening || !this.analyser) return null;

        // Get time domain data (waveform) for pitch detection
        this.analyser.getFloatTimeDomainData(this.buffer);
        
        // Detect pitch
        const frequency = this.detectPitch(this.buffer);
        
        // Pitchfinder returns null if no pitch is detected or confidence is low
        if (frequency) {
            return {
                frequency: frequency, // Hz
                note: this.frequencyToNoteName(frequency),
                timestamp: this.audioContext.currentTime
            };
        }
        return null;
    }

    // Helper: Convert frequency to note name (e.g., 440 -> A4)
    frequencyToNoteName(frequency) {
        const noteStrings = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
        const pitch = Math.round(69 + 12 * Math.log2(frequency / 440));
        const octave = Math.floor(pitch / 12) - 1;
        const noteIndex = pitch % 12;
        return noteStrings[noteIndex] + octave;
    }
}

export default new AudioEngine();
