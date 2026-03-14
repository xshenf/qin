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

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue';
import { FONT_DIRECTORY, SOUND_FONT_URL } from '../config/alphaTabConfig';
import * as alphaTab from '@coderline/alphatab';
import PracticeEngine from '../engine/PracticeEngine';

const scoreContainer = ref(null);
let api = null;
let isPlayerReady = false; // 标记播放器是否真正准备好
let apiVersion = 0; // 用于区分不同的 API 实例，防止旧事件闭包干扰

const props = defineProps({
  fileUrl: {
    type: [String, Object],
    default: ''
  },
  zoom: {
    type: Number,
    default: 100
  },
  staveProfile: {
    type: String,
    default: 'default'
  },
  playbackSpeed: {
    type: Number,
    default: 100
  }
});

const emit = defineEmits([
  'playerReady',
  'playerFinished',
  'playedBeatChanged',
  'activeBeatsChanged',
  'scoreLoaded',
  'playerPositionChanged',
  'isPlayingChanged'
]);

// ========== 核心：创建和销毁 AlphaTab API ==========

const destroyApi = () => {
  if (api) {
    try {
      api.destroy();
    } catch (e) {
      console.warn("AlphaTab destroy error (ignored):", e.message);
    }
    api = null;
  }
  isPlayerReady = false;
};

const initAlphaTab = () => {
  if (!scoreContainer.value) {
    console.error("ScoreContainer not found!");
    return;
  }

  // 防止重复初始化
  if (api) {
    console.log("AlphaTab API already exists, skipping init");
    return;
  }

  console.log("Initializing AlphaTab...");

  // 每次创建新实例时递增版本号
  apiVersion++;
  const myVersion = apiVersion;

  const settings = {
    core: {
      fontDirectory: FONT_DIRECTORY,
      useWorkers: false
    },
    importer: {
      encoding: 'gbk'
    },
    display: {
      layoutMode: 0, // Page
      scale: props.zoom / 100,
      staveProfile: getStaveProfile(props.staveProfile)
    },
    player: {
      enablePlayer: true,
      enableCursor: true,
      enableAnimatedBeatCursor: true,
      enableElementHighlighting: true,
      soundFont: SOUND_FONT_URL,
      scrollElement: scoreContainer.value.parentElement,
      scrollSpeed: 10,
      scrollOffsetX: 0,
    }
  };

  if (props.fileUrl) {
    settings.file = props.fileUrl;
  }

  try {
    api = new alphaTab.AlphaTabApi(scoreContainer.value, settings);
    api.playbackSpeed = props.playbackSpeed / 100;
    console.log("AlphaTab API created successfully");
  } catch (e) {
    console.error("Error creating AlphaTab API:", e);
    api = null;
    return;
  }

  // 绑定事件 - 所有事件回调内部都检查版本号，防止旧闭包干扰
  api.scoreLoaded.on((score) => {
    if (apiVersion !== myVersion) return;
    emit('scoreLoaded', score);
  });

  api.playerStateChanged.on((args) => {
    if (apiVersion !== myVersion) return;
    // args.state: 0=Stopped, 1=Playing, 2=Paused
    const isPlaying = args.state === 1;
    emit('isPlayingChanged', isPlaying);
  });

  api.playerReady.on(() => {
    if (apiVersion !== myVersion) return;
    console.log("Player ready");
    isPlayerReady = true;
    PracticeEngine.attachScore(api);
    emit('playerReady', api);
  });

  api.playerFinished.on(() => {
    if (apiVersion !== myVersion) return;
    emit('playerFinished');
  });

  api.playedBeatChanged.on((beat) => {
    if (apiVersion !== myVersion) return;
    emit('playedBeatChanged', beat);
    
    // 推送音符给练习引擎
    if (beat && beat.notes) {
      const notes = beat.notes.map(n => ({
        id: n.id,
        fret: n.value, 
        string: n.string,
        startTick: beat.start,
        duration: beat.duration,
        ref: n
      }));
      PracticeEngine.updateExpectedNotes(notes);
    }
  });
};

// ========== Marker 标记逻辑 ==========

const markers = ref([]);

const markNote = (note, status) => {
  if (!api || !note) return;
  
  const noteObj = note.ref ? note.ref : note;
  if (!noteObj || typeof noteObj !== 'object') return;

  try {
    const NoteStyle = alphaTab.model.NoteStyle;
    const NoteSubElement = alphaTab.model.NoteSubElement;
    const Color = alphaTab.model.Color;

    if (!NoteStyle || !NoteSubElement || !Color) return;

    if (!noteObj.style) {
      noteObj.style = new NoteStyle();
    }
    
    let atColor;
    if (status === 'hit') {
      atColor = new Color(255, 66, 184, 131); 
    } else {
      atColor = new Color(255, 255, 0, 0);
    }
    
    noteObj.style.colors.set(NoteSubElement.NoteHead, atColor);
    noteObj.style.colors.set(NoteSubElement.Stem, atColor);
    requestRender();
  } catch (e) {
    console.error("Error coloring note:", e);
  }
};

let renderPending = false;
const requestRender = () => {
  if (!api || renderPending) return;
  renderPending = true;
  requestAnimationFrame(() => {
    if (api) {
      api.render();
    }
    renderPending = false;
  });
};

// ========== 对外暴露的方法 ==========

const playPause = () => {
  if (!api) return;
  if (!isPlayerReady) {
    console.warn("Player not ready yet, ignoring playPause");
    return;
  }
  try {
    api.playPause();
  } catch (e) {
    console.warn("Play/Pause error:", e);
  }
};

const stop = () => {
  if (!api) return;
  if (!isPlayerReady) return;
  try {
    api.pause();
    api.tickPosition = 0; 
  } catch (e) {
    console.warn("Error stopping player:", e);
  }
};

const clear = () => {
  // 销毁 API 实例
  destroyApi();
  // 清空容器内容
  if (scoreContainer.value) {
    scoreContainer.value.innerHTML = '';
  }
  markers.value = [];
};

const getApi = () => api;

const loadFile = (file) => {
  // 确保 API 存在，如果之前被 clear() 销毁过，需要重新初始化
  if (!api) {
    initAlphaTab();
  }
  if (!api) {
    console.error("Failed to create AlphaTab API for loading file");
    return;
  }

  // 重置播放就绪状态，防止在加载期间触发播放
  isPlayerReady = false;

  const reader = new FileReader();
  reader.onload = (e) => {
    if (e.target?.result && api) {
      api.load(e.target.result);
    }
  };
  reader.readAsArrayBuffer(file);
};

// ========== 生命周期 ==========

let resizeObserver = null;

onMounted(() => {
  console.log("ScoreViewer Mounted");
  
  // 使用 ResizeObserver 检测容器何时可见
  resizeObserver = new ResizeObserver((entries) => {
    for (const entry of entries) {
      if (entry.contentRect.width > 0 && entry.contentRect.height > 0) {
        // 仅在 API 未创建时执行初始化
        if (!api) {
          initAlphaTab();
        }
      }
    }
  });
  
  if (scoreContainer.value) {
    resizeObserver.observe(scoreContainer.value);
  }
  
  // 如果已经可见，立即初始化
  if (scoreContainer.value) {
    const rect = scoreContainer.value.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      initAlphaTab();
    }
  }
});

onUnmounted(() => {
  console.log("ScoreViewer Unmounted");
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  destroyApi();
});

// ========== watchers ==========

watch(
  () => props.fileUrl,
  (newUrl) => {
    if (newUrl && api) {
      isPlayerReady = false;
      api.load(newUrl);
    }
  }
);

watch(() => props.zoom, (val) => {
  if (api) {
    api.settings.display.scale = val / 100;
    api.updateSettings();
    api.render();
  }
});

watch(() => props.staveProfile, (val) => {
  if (api) {
    api.settings.display.staveProfile = getStaveProfile(val);
    api.updateSettings();
    api.render();
  }
});

watch(() => props.playbackSpeed, (val) => {
  if (api) {
    api.playbackSpeed = val / 100;
  }
});

// ========== 辅助函数 ==========

const getStaveProfile = (profile) => {
  const map = {
    'default': 0, // Default (Score + Tab)
    'score': 2,   // Score only
    'tab': 3      // Tab only
  };
  return map[profile] || 0;
};

const renderTrack = (track) => {
  if (!api) return;
  
  let targetTracks = [];
  if (typeof track === 'number') {
    if (api.score && api.score.tracks && api.score.tracks[track]) {
      targetTracks = [api.score.tracks[track]];
    }
  } else if (typeof track === 'object') {
    targetTracks = [track];
  }
  
  if (targetTracks.length > 0) {
    api.renderTracks(targetTracks);
  }
};

const testCursorMove = () => {
  if (!api) return;
  try {
    const currentTick = api.tickPosition;
    const newTick = currentTick + 960;
    api.tickPosition = newTick;
  } catch (e) {
    console.warn("TEST JUMP ERROR:", e);
  }
};

defineExpose({
  playPause,
  stop,
  clear,
  loadFile,
  getApi,
  markNote,
  renderTrack,
  testCursorMove
});
</script>

<style scoped>
.score-wrapper {
  width: 100%;
  flex: 1;
  overflow-x: hidden;
  overflow-y: auto;
  background: white;
  box-sizing: border-box;
  position: relative;
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
  background: rgba(33, 33, 168, 0.27) !important;
  will-change: left, top, width, height;
}

.at-cursor-beat {
  background: #0a47a499 !important;
  will-change: left, top;
  z-index: -100;
}

.at-highlight * {
  fill: #42b883 !important;
  stroke: #42b883 !important;
}
</style>
