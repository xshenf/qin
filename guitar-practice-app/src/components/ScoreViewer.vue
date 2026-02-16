<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue';
import * as alphaTab from '@coderline/alphatab';

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
      scrollElement: scoreContainer.value.parentElement
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
  });

  api.activeBeatsChanged.on((args) => {
    emit('activeBeatsChanged', args);
  });

  api.playerPositionChanged.on((args) => {
    emit('playerPositionChanged', args);
  });

  // Load file if URL provided
  if (props.fileUrl) {
    console.log('Loading score from:', props.fileUrl);
    api.load(props.fileUrl);
  }
};

onMounted(() => {
  initAlphaTab();
});

onUnmounted(() => {
  if (api) {
    api.destroy();
  }
});

// Watch for fileUrl changes
watch(() => props.fileUrl, (newVal) => {
  if (api && newVal) {
    api.load(newVal);
  }
});

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

defineExpose({
  playPause,
  stop,
  loadFile,
  getApi
});
</script>

<template>
  <div class="score-wrapper">
    <div ref="scoreContainer" class="score-container"></div>
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
}
.score-container {
  min-height: 100%;
  width: 100%;
  box-sizing: border-box;
  overflow-x: hidden;
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
