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

        // 音量阈值（降低到0.001以最大化移动端灵敏度）
        const volumeThreshold = 0.001;
        if (averageVolume < volumeThreshold) {
            return null; // 音量太小，忽略（可能是环境噪音）
        }

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
                // 频率超出吉他范围，忽略（可能是检测错误或倍频）
                console.log(`Ignored invalid frequency: ${frequency}Hz`);
                return null;
            }

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
