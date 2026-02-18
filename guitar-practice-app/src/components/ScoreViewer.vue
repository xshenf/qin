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
  if (!scoreContainer.value) {
    console.error("ScoreContainer not found!");
    return;
  }
  console.log("Initializing AlphaTab...", props.fileUrl);

  if (api) api.destroy();

  const settings = {
    file: props.fileUrl || '', // Ensure valid file url is passed
    core: {
      // Tell AlphaTab where to find fonts (served from public/)
      fontDirectory: '/font/',
      useWorkers: false
    },
    importer: {
      encoding: 'gbk'
    },
    display: {
      layoutMode: 0, // Page
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

  try {
    api = new alphaTab.AlphaTabApi(scoreContainer.value, settings);
    console.log("AlphaTab API created successfully");
    
    // Debug events
    api.error.on((e) => {
      console.error('AlphaTab Error Event:', e);
    });
    api.renderFinished.on(() => {
      console.log('AlphaTab Render Finished');
    });
  } catch (e) {
    console.error("Error creating AlphaTab API:", e);
  }

  // Events - using correct AlphaTab v1.8 event names
  api.scoreLoaded.on((score) => {
    console.log('Score loaded:', score.title);
    emit('scoreLoaded', score);
  });

  api.playerReady.on(() => {
    console.log('Player ready');
    PracticeEngine.attachScore(api); // 连接乐谱API到练习引擎
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
  console.log(`Coloring note: ${status}`, note);
  
  if (!note.ref) {
      console.warn("Note reference missing");
      return;
  }

  // Use AlphaTab NoteStyle to change color
  // Status: hit (green), miss (red)
  const color = status === 'hit' ? 'rgba(66, 184, 131, 1)' : 'rgba(255, 0, 0, 1)';
  
  // Note: We need to ensure we have access to AlphaTab model classes.
  // Assuming 'api' has access or we can just set properties if they are simple objects.
  // But AlphaTab usually requires class instances for Style.
  
  // Let's try to set style on the note.
  try {
      // Create style if missing. 
      // We process the note.ref (AlphaTab Note object)
      const noteObj = note.ref;
      
      // We need alphaTab namespace. 
      // imports are: import * as alphaTab from '@coderline/alphatab';
      
      const NoteStyle = alphaTab.model.NoteStyle;
      const NoteSubElement = alphaTab.model.NoteSubElement;
      const Color = alphaTab.model.Color;

      if (!NoteStyle || !NoteSubElement || !Color) {
          console.error("AlphaTab model classes missing.", { NoteStyle, NoteSubElement, Color });
          return;
      }

      if (!noteObj.style) {
          noteObj.style = new NoteStyle();
      }
      
      // Parse color string to r,g,b,a? 
      // AlphaTab Color constructor: (a, r, g, b)
      let atColor;
      if (status === 'hit') {
          atColor = new Color(255, 66, 184, 131); 
      } else {
          atColor = new Color(255, 255, 0, 0);
      }
      
      noteObj.style.colors.set(NoteSubElement.NoteHead, atColor);
      noteObj.style.colors.set(NoteSubElement.Stem, atColor); // also color stem

      // Trigger re-render
      // We should debounce render if possible, but for now direct call
      api.render();
      
  } catch (e) {
      console.error("Error coloring note:", e);
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
// ...
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

watch(
  () => props.fileUrl,
  (newUrl) => {
    if (newUrl && api) {
      console.log("Loading new file from watch:", newUrl);
      api.load(newUrl);
    }
  }
);

const renderTrack = (track) => {
  if (!api) return;
  console.log("Rendering track:", track);
  // AlphaTab API: renderTracks accepts an array of track objects or track indexes?
  // Documentation says: renderTracks(tracks: Track[])
  // So we need to pass the track object(s) we want to render.
  // If track is an index, we get it from api.score.tracks
  
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
// ...

// Expose methods
defineExpose({
  playPause,
  stop,
  loadFile,
  getApi,
  markNote,
  renderTrack
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
  background: rgba(33, 33, 168, 0.27) !important;
  will-change: left, top, width, height;
}

.at-cursor-beat {
  background: #0a47a499 !important; /* 使用主题色 */
  will-change: left, top;
  z-index: -100;
}

.at-highlight * {
  fill: #42b883 !important;
  stroke: #42b883 !important;
}
</style>
