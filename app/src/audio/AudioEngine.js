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
        this.bufferSize = 8192; // 增大以提高低频分辨率，特别是移动端

        // Attack/Transient detection
        this.lastVolume = 0;
        this.lastAttackTime = 0;
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

    async startMicrophone(options = {}) {
        const { bassBoost = false } = options;

        if (!this.audioContext) await this.init();

        try {
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
            }

            // 音频约束
            // 如果开启低音增强（通常是移动端），关闭降噪以避免滤除低频
            // 否则使用默认降噪配置（桌面端）
            const constraints = {
                audio: {
                    echoCancellation: !bassBoost, // 移动端关闭回声消除
                    noiseSuppression: !bassBoost, // 移动端关闭降噪
                    autoGainControl: !bassBoost,  // 移动端关闭自动增益
                    channelCount: 1
                },
                video: false
            };

            // Request microphone access
            this.mediaStream = await navigator.mediaDevices.getUserMedia(constraints);

            // Create source node from stream
            const source = this.audioContext.createMediaStreamSource(this.mediaStream);

            // === 音频滤波器链 ===

            // 1. 高通滤波器
            const highpassFilter = this.audioContext.createBiquadFilter();
            highpassFilter.type = 'highpass';
            // 开启低音增强时降低到30Hz，否则使用50Hz
            highpassFilter.frequency.value = bassBoost ? 30 : 50;
            highpassFilter.Q.value = bassBoost ? 0.5 : 0.7;

            // 2. 低通滤波器
            const lowpassFilter = this.audioContext.createBiquadFilter();
            lowpassFilter.type = 'lowpass';
            lowpassFilter.frequency.value = 5000;
            lowpassFilter.Q.value = 0.7;

            // 构建连接链路
            if (bassBoost) {
                // 开启低音增强：Source -> HighPass -> LowShelf -> LowPass -> Analyser
                const lowShelf = this.audioContext.createBiquadFilter();
                lowShelf.type = 'lowshelf';
                lowShelf.frequency.value = 120;
                lowShelf.gain.value = 12; // +12dB

                source.connect(highpassFilter);
                highpassFilter.connect(lowShelf);
                lowShelf.connect(lowpassFilter);
                lowpassFilter.connect(this.analyser);
            } else {
                // 标准模式：Source -> HighPass -> LowPass -> Analyser
                source.connect(highpassFilter);
                highpassFilter.connect(lowpassFilter);
                lowpassFilter.connect(this.analyser);
            }

            this.isListening = true;
            console.log(`Microphone started (Bass Boost: ${bassBoost ? 'ON' : 'OFF'})`);
        } catch (e) {
            console.error("Failed to access microphone:", e);
            throw e;
        }
    }

    async stopMicrophone() {
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
            this.mediaStream = null;
        }

        // 挂起 AudioContext 以释放硬件资源，消除录音指示器
        if (this.audioContext && this.audioContext.state === 'running') {
            try {
                await this.audioContext.suspend();
            } catch (e) {
                console.error("Failed to suspend AudioContext:", e);
            }
        }

        this.isListening = false;
        console.log("Microphone stopped.");
    }

    getPitch() {
        if (!this.isListening || !this.analyser) return null;

        // Get time domain data (waveform) for pitch detection
        this.analyser.getFloatTimeDomainData(this.buffer);

        // === 噪音门限 - 计算音量，忽略弱信号 ===
        let sum = 0;
        for (let i = 0; i < this.buffer.length; i++) {
            sum += Math.abs(this.buffer[i]);
        }
        const averageVolume = sum / this.buffer.length;

        // 音量阈值（调高到0.005过滤底噪和摩擦音）
        const volumeThreshold = 0.005;
        if (averageVolume < volumeThreshold) {
            this.lastVolume = averageVolume;
            return null; // 音量太小，忽略
        }

        // === 瞬态(Attack)检测 - 寻找拨弦的瞬间 ===
        let isAttack = false;
        const now = this.audioContext.currentTime;
        // 如果当前音量是上一帧的 1.5 倍以上，并且距离上次拨弦超过 100ms
        if (averageVolume > this.lastVolume * 1.5 && (now - this.lastAttackTime > 0.1)) {
            isAttack = true;
            this.lastAttackTime = now;
        }
        this.lastVolume = averageVolume;

        // Detect pitch
        const frequency = this.detectPitch(this.buffer);

        // Pitchfinder returns null if no pitch is detected or confidence is low
        if (frequency) {
            // === 频率范围验证 - 过滤错误检测 ===
            // 吉他频率范围：E2(82Hz) 到 E6 22品(1318Hz)
            // 扩大范围到 50Hz - 2000Hz 以涵盖6弦和泛音
            const minFreq = 50;
            const maxFreq = 2000;

            if (frequency < minFreq || frequency > maxFreq) {
                // 频率超出吉他范围，忽略
                return null;
            }

            const pitchInfo = this.getNoteDetail(frequency);
            return {
                frequency: frequency, // Hz
                note: pitchInfo.note,
                cents: pitchInfo.cents,
                timestamp: this.audioContext.currentTime,
                isAttack: isAttack
            };
        }
        return null;
    }

    // Helper: Convert frequency to note name and cents
    getNoteDetail(frequency) {
        const noteStrings = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
        // MIDI Note = 69 + 12 * log2(f / 440)
        const midiFloat = 69 + 12 * Math.log2(frequency / 440);
        const midi = Math.round(midiFloat);
        const deviation = midiFloat - midi;
        const cents = Math.floor(deviation * 100);

        const octave = Math.floor(midi / 12) - 1;
        const noteIndex = midi % 12;
        const noteName = noteStrings[noteIndex] + octave;

        return {
            note: noteName,
            cents: cents,
            midi: midi
        };
    }

    /**
     * Polyphonic Pitch Detection using Spectral Peak Analysis
     * @returns {Array} Array of detected notes [{ note, frequency, cents, amplitude }]
     */
    getPolyphonicPitch() {
        if (!this.isListening || !this.analyser) return [];

        // 1. Get Frequency Data
        const bufferLength = this.analyser.frequencyBinCount; // fftSize / 2
        const dataArray = new Float32Array(bufferLength);
        this.analyser.getFloatFrequencyData(dataArray);

        // 2. Find Peaks (Simple Peak Picking)
        // Threshold: -70dB (configurable, silence is usually -100dB)
        const threshold = -70; // 使用稳定器过滤噪声，此处保持灵敏
        const peaks = [];
        const sampleRate = this.sampleRate;
        const fftSize = this.analyser.fftSize;
        const binSize = sampleRate / fftSize;

        // Skip very low frequencies (< 70Hz)
        const startBin = Math.floor(70 / binSize);
        // Skip very high frequencies (> 2000Hz, guitar range)
        const endBin = Math.floor(2000 / binSize);

        for (let i = startBin; i < endBin; i++) {
            const val = dataArray[i];
            if (val > threshold) {
                // Check if it's a local maximum
                if (dataArray[i - 1] < val && dataArray[i + 1] < val) {
                    // Parabolic Interpolation for better accuracy
                    const alpha = dataArray[i - 1];
                    const beta = val;
                    const gamma = dataArray[i + 1];

                    const p = 0.5 * (alpha - gamma) / (alpha - 2 * beta + gamma);
                    const interpolatedBin = i + p;

                    peaks.push({
                        bin: interpolatedBin,
                        frequency: interpolatedBin * binSize,
                        magnitude: val
                    });
                }
            }
        }

        // 3. Sort by magnitude (loudest first)
        peaks.sort((a, b) => b.magnitude - a.magnitude);

        // 3.5 Relative Peak Filter: discard peaks more than 20dB below the loudest
        if (peaks.length > 0) {
            const loudest = peaks[0].magnitude;
            const relativeThreshold = 20; // dB
            const filtered = peaks.filter(p => (loudest - p.magnitude) < relativeThreshold);
            peaks.length = 0;
            peaks.push(...filtered);
        }

        // 4. Filter Harmonics
        // If we find a peak P, likely its harmonics 2*P, 3*P are also peaks.
        // We want to keep the fundamental (usually the lowest frequency for a given note, 
        // but sometimes harmonics are louder).
        // Strategy: Iterate sorted peaks. If a peak matches a harmonic of an already selected peak, discard it?
        // Wait, if we play a chord (C3 + E3), E3 is NOT a harmonic of C3.
        // But E3 might be a harmonic of a lower C2?
        // Simple Harmonic Filter:
        // Take loudest. Assume it's a note.
        // Remove weaker peaks that are integer multiples of this frequency (with tolerance).

        const detectedNotes = [];
        const maxPolyphony = 4; // 最多识别4个基频

        const isHarmonic = (f1, f2) => {
            // Check if f2 is a multiple of f1
            const ratio = f2 / f1;
            const nearestInt = Math.round(ratio);
            if (nearestInt < 2) return false; // Not a harmonic (or is fundamental)
            // Tolerance: 2%
            return Math.abs(ratio - nearestInt) < 0.03;
        };

        // We also need to handle "Octave errors". 
        // Sometimes the 2nd harmonic is louder than fundamental.
        // For now, simple greedy approach.

        const finalizedPeaks = [];

        // Iterative selection
        while (peaks.length > 0 && finalizedPeaks.length < maxPolyphony) {
            const currentPeak = peaks.shift(); // Loudest remaining

            let isArtifact = false;
            for (let i = 0; i < finalizedPeaks.length; i++) {
                const existing = finalizedPeaks[i];

                // Check if current is harmonic of existing (Existing is louder/already picked)
                if (isHarmonic(existing.frequency, currentPeak.frequency)) {
                    isArtifact = true;
                    break;
                }

                // IF existing is actually a harmonic of current (Missing Fundamental problem)
                // e.g. Existing=220Hz (loud), Current=110Hz (quieter). We should REPLACE existing with current!
                if (isHarmonic(currentPeak.frequency, existing.frequency)) {
                    // Replace the harmonic with the fundamental
                    finalizedPeaks[i] = currentPeak;
                    isArtifact = true; // We handled it, don't push again
                    break;
                }
            }

            if (!isArtifact) {
                finalizedPeaks.push(currentPeak);
            }

            // Remove harmonics of the current chosen fundamental from candidates
            for (let i = peaks.length - 1; i >= 0; i--) {
                if (isHarmonic(currentPeak.frequency, peaks[i].frequency)) {
                    peaks.splice(i, 1);
                }
            }
        }

        // 5. Convert to Notes
        return finalizedPeaks.map(p => {
            const details = this.getNoteDetail(p.frequency);
            return {
                frequency: p.frequency,
                magnitude: p.magnitude,
                ...details
            };
        });
    }
}

export default new AudioEngine();
