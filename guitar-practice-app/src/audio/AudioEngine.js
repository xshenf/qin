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

    async startMicrophone() {
        if (!this.audioContext) await this.init();

        try {
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
            }

            // 音频约束 - 针对移动端低频优化
            // 关闭噪音抑制和自动增益，它们可能过滤/压制低频
            const constraints = {
                audio: {
                    echoCancellation: false,      // 关闭回声消除
                    noiseSuppression: false,      // 关闭噪音抑制（保留低频）
                    autoGainControl: false,       // 关闭自动增益（避免压制低频）
                    channelCount: 1               // 单声道
                },
                video: false
            };

            // Request microphone access
            this.mediaStream = await navigator.mediaDevices.getUserMedia(constraints);

            // Create source node from stream
            const source = this.audioContext.createMediaStreamSource(this.mediaStream);

            // === 添加音频滤波器链（针对移动端低频优化） ===

            // 1. 高通滤波器 - 去除极低频噪音（< 30Hz）
            const highpassFilter = this.audioContext.createBiquadFilter();
            highpassFilter.type = 'highpass';
            highpassFilter.frequency.value = 30; // 降低到30Hz给低音更多余地
            highpassFilter.Q.value = 0.5;

            // 2. 低频增强 - 提升吉他低音弦（60-150Hz）
            const lowShelf = this.audioContext.createBiquadFilter();
            lowShelf.type = 'lowshelf';
            lowShelf.frequency.value = 120; // 中心频率
            lowShelf.gain.value = 12; // 提升12dB补偿手机麦克风

            // 3. 低通滤波器 - 去除高频噪音（> 5000Hz）
            const lowpassFilter = this.audioContext.createBiquadFilter();
            lowpassFilter.type = 'lowpass';
            lowpassFilter.frequency.value = 5000;
            lowpassFilter.Q.value = 0.7;

            // 连接: source -> 高通 -> 低频增强 -> 低通 -> analyser
            source.connect(highpassFilter);
            highpassFilter.connect(lowShelf);
            lowShelf.connect(lowpassFilter);
            lowpassFilter.connect(this.analyser);

            this.isListening = true;
            console.log("Microphone started with noise suppression enabled.");
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
