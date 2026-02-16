<script setup>
import { ref } from 'vue';
import ScoreViewer from './components/ScoreViewer.vue';
import AudioEngine from './audio/AudioEngine';
import PracticeEngine from './engine/PracticeEngine';
// Optional: import AlphaTab styles if needed, but usually they are injected or minimal?
// import '@coderline/alphatab/dist/alphatab.css'; // Check if this exists

const scoreViewer = ref(null);
const isMicActive = ref(false);
const detectedPitch = ref('--');
const detectedNote = ref('--');

// Playback state
const isPlaying = ref(false);

// Polling for UI feedback
let uiInterval = null;

const toggleMic = async () => {
  if (isMicActive.value) {
    AudioEngine.stopMicrophone();
    isMicActive.value = false;
    clearInterval(uiInterval);
  } else {
    try {
      await AudioEngine.startMicrophone();
      isMicActive.value = true;
      
      // Visualize pitch
      uiInterval = setInterval(() => {
        const pitch = AudioEngine.getPitch();
        if (pitch) {
          detectedPitch.value = pitch.frequency.toFixed(1) + ' Hz';
          detectedNote.value = pitch.note;
        } else {
          detectedPitch.value = '--';
          detectedNote.value = '--';
        }
      }, 100);

    } catch (e) {
      alert("Microphone access failed: " + e.message);
    }
  }
};

// File handling
const handleFileSelect = (event) => {
  const file = event.target.files[0];
  if (file && scoreViewer.value) {
    scoreViewer.value.loadFile(file);
  }
};

// Playback controls
const togglePlayback = () => {
  if (scoreViewer.value) {
    scoreViewer.value.playPause();
    isPlaying.value = !isPlaying.value; // Note: Better to sync with alphaTab events
  }
};

const handleScoreReady = (api) => {
  console.log("Score loaded!", api);
  PracticeEngine.attachScore(api);
  
  // Hook into Practice Engine update loop if not already
  // practiceEngine.start(); // We might play manually for now
};

const handleBeatChanged = (beat) => {
  // console.log("Beat:", beat);
};

// URL to a public GP file or local asset. AlphaTab has a demo file.
// We'll use a cloud file for test if possible, or just empty.
const demoFile = 'https://www.alphatab.net/files/canon.gp'; 
</script>

<template>
  <div class="app-container">
    <header>
      <h1>Guitar Practice</h1>
      
      <div class="file-controls">
        <input type="file" accept=".gp,.gp3,.gp4,.gp5,.gpx" @change="handleFileSelect" />
        <button @click="togglePlayback">
          {{ isPlaying ? 'Pause' : 'Play Score' }}
        </button>
      </div>

      <div class="audio-controls">
        <button @click="toggleMic" :class="{ active: isMicActive }">
          {{ isMicActive ? 'Mic ON' : 'Mic OFF' }}
        </button>
        <div class="monitor">
          <div class="monitor-item">
            <span class="label">Pitch</span>
            <span class="value">{{ detectedPitch }}</span>
          </div>
          <div class="monitor-item">
            <span class="label">Note</span>
            <span class="value">{{ detectedNote }}</span>
          </div>
        </div>
      </div>
    </header>

    <main>
      <ScoreViewer 
        ref="scoreViewer" 
        :file-url="demoFile"
        @playerReady="handleScoreReady"
        @beatChanged="handleBeatChanged"
      />
    </main>
  </div>
</template>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding: 0;
  background: #1e1e1e; /* Dark theme */
  color: #fff;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #2d2d2d;
  padding: 15px 20px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.3);
  z-index: 10;
}

h1 {
  font-size: 1.2rem;
  margin: 0;
  color: #42b883;
}

.file-controls, .audio-controls {
  display: flex;
  gap: 15px;
  align-items: center;
}

.monitor {
  display: flex;
  gap: 15px;
  background: #000;
  padding: 5px 15px;
  border-radius: 4px;
  border: 1px solid #444;
}

.monitor-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.monitor-item .label {
  font-size: 0.7rem;
  color: #888;
}

.monitor-item .value {
  font-family: monospace;
  font-size: 1rem;
  color: #42b883;
}

button {
  padding: 8px 16px;
  background: #444;
  color: white;
  border: 1px solid #555;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

button:hover {
  background: #555;
}

button.active {
  background: #e74c3c;
  border-color: #c0392b;
}

main {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
</style>
