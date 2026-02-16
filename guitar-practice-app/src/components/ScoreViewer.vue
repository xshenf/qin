<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue';
import * as alphaTab from '@coderline/alphatab';
import PracticeEngine from '../engine/PracticeEngine';

const scoreContainer = ref(null);
let api = null;

const props = defineProps({
  fileUrl: {
    type: [String, Object],
    default: ''
  }
});

const emit = defineEmits([
  'playerReady',
  'playerFinished',
  'playedBeatChanged',
  'activeBeatsChanged',
  'scoreLoaded',
  'playerPositionChanged'
]);

const initAlphaTab = () => {
  if (!scoreContainer.value) return;
  if (api) api.destroy();

  const settings = {
    core: {
      // Tell AlphaTab where to find fonts (served from public/)
      fontDirectory: '/font/',
    },
    player: {
      enablePlayer: true,
      enableCursor: true,
      enableAnimatedBeatCursor: true,
      enableElementHighlighting: true,
      // Served from public/soundfont/
      soundFont: '/soundfont/sonivox.sf2',
      scrollElement: scoreContainer.value.parentElement,
      scrollSpeed: 10,        // 调整滚动速度 (更小的值 = 更快的动画?) 尝试 100ms
      scrollOffsetX: 0,
    }
  };

  api = new alphaTab.AlphaTabApi(scoreContainer.value, settings);

  // Events - using correct AlphaTab v1.8 event names
  api.scoreLoaded.on((score) => {
    console.log('Score loaded:', score.title);
    emit('scoreLoaded', score);
  });

  api.playerReady.on(() => {
    console.log('Player ready');
    emit('playerReady', api);
  });

  api.playerFinished.on(() => {
    emit('playerFinished');
  });

  api.playedBeatChanged.on((beat) => {
    emit('playedBeatChanged', beat);
    
    // Push notes to PracticeEngine
    if (beat && beat.notes) {
      const notes = beat.notes.map(n => ({
        id: n.id,
        fret: n.value, 
        string: n.string,
        startTick: beat.start,
        duration: beat.duration,
        ref: n // Keep reference to AlphaTab note object
      }));
      PracticeEngine.updateExpectedNotes(notes);
    }
  });

  // ... (other events)
};

// ...

// Marker logic
const markers = ref([]); // Array of { style, class }

const markNote = (note, status) => {
  if (!api || !note) return;
  // AlphaTab 1.3+ has boundsLookup. 
  // note is the AlphaTab model object.
  try {
    const bounds = api.renderer.boundsLookup.getNoteBounds(note);
    if (bounds) {
       // bounds: x, y, w, h
       markers.value.push({
         style: {
           left: bounds.x + 'px',
           top: bounds.y + 'px',
           width: bounds.w + 'px',
           height: bounds.h + 'px'
         },
         class: status === 'hit' ? 'marker-hit' : 'marker-miss'
       });
    }
  } catch (e) {
    console.error("Error marking note:", e);
  }
};

onMounted(() => {
  initAlphaTab();
});

// ...

// Expose methods
const playPause = () => api?.playPause();
const stop = () => api?.stop();
const getApi = () => api;
const loadFile = (file) => {
  if (!api) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    if (e.target?.result) {
      api.load(e.target.result);
    }
  };
  reader.readAsArrayBuffer(file);
};

// Expose methods
defineExpose({
  playPause,
  stop,
  loadFile,
  getApi,
  markNote
});
</script>

<template>
  <div class="score-wrapper">
    <div ref="scoreContainer" class="score-container"></div>
    <!-- Markers Overlay -->
    <div class="markers-overlay">
      <div 
        v-for="(marker, index) in markers" 
        :key="index"
        :class="marker.class"
        :style="marker.style"
      ></div>
    </div>
  </div>
</template>

<style scoped>
.score-wrapper {
  width: 100%;
  flex: 1;
  overflow-x: hidden;
  overflow-y: auto;
  background: white;
  box-sizing: border-box;
  position: relative; /* For markers overlay */
}
.score-container {
  min-height: 100%;
  width: 100%;
  box-sizing: border-box;
  overflow-x: hidden;
}

.markers-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 5;
}

.marker-hit {
  position: absolute;
  background: rgba(66, 184, 131, 0.4);
  border: 1px solid #42b883;
  border-radius: 4px;
}

.marker-miss {
  position: absolute;
  background: rgba(255, 69, 58, 0.4);
  border: 1px solid #ff453a;
  border-radius: 4px;
}
</style>

<style>
/* AlphaTab 全局样式 - 播放高亮 */
.at-cursor-bar {
  background: rgba(255, 242, 0, 0.2) !important;
  will-change: left, top, width, height;
}

.at-cursor-beat {
  background: #42b883 !important; /* 使用主题色 */
  width: 2px !important;
  will-change: left, top;
  z-index: 10;
}

.at-highlight * {
  fill: #42b883 !important;
  stroke: #42b883 !important;
}
</style>
