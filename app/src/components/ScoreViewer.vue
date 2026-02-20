<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue';
import { soundFontUrl } from '../utils/soundFont';
import { FONT_DIRECTORY } from '../config/alphaTabConfig';
import * as alphaTab from '@coderline/alphatab';
import PracticeEngine from '../engine/PracticeEngine';

const scoreContainer = ref(null);
let api = null;

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
  'scoreLoaded',
  'playerPositionChanged',
  'isPlayingChanged'
]);

const initAlphaTab = () => {
  if (!scoreContainer.value) {
    console.error("ScoreContainer not found!");
    return;
  }
  // Check if we already initialized for this URL effectively?
  // But we want to re-init if needed.
  
  console.log("Initializing AlphaTab...", props.fileUrl);

  if (api) {
    try {
        api.destroy();
    } catch(e) {
        console.warn("Cleanup error", e);
    }
    // Also remove any existing content in container just in case
    if (scoreContainer.value) {
        scoreContainer.value.innerHTML = '';
    }
  }

  const settings = {
    // file: props.fileUrl || '', // Ensure valid file url is passed

    core: {
      // Tell AlphaTab where to find fonts (Use CDN to reduce build size)
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
      enableElementHighlighting: true,
      // Use CDN for SoundFont to reduce build size (1.3MB)
      soundFont: soundFontUrl.value,
      scrollElement: scoreContainer.value.parentElement,
      scrollSpeed: 10,        // 调整滚动速度 (更小的值 = 更快的动画?) 尝试 100ms
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
    
    // Debug events - commented out to reduce noise
    /*
    api.error.on((e) => {
      console.error('AlphaTab Error Event:', e);
    });
    api.renderFinished.on(() => {
      console.log('AlphaTab Render Finished');
    });
    */
  } catch (e) {
    console.error("Error creating AlphaTab API:", e);
  }

  // Attach events
  
  // NOTE: AlphaTabApi.on() adds listeners. When we create a NEW api instance,
  // the old listeners are garbage collected with the old instance (assuming destroy() worked).
  // However, if destroy() failed or if we bound to something global, we'd have issues.
  // The 'api' variable is local to this scope but updated in the outer 'api' let var.
  
  // Events - using correct AlphaTab v1.8 event names
  api.scoreLoaded.on((score) => {
    // console.log('Score loaded:', score.title);
    emit('scoreLoaded', score);
  });

  api.playerStateChanged.on((args) => {
    // args.state where 0=Stopped, 1=Playing, 2=Paused
    // We consider 'Playing' (1) as isPlaying=true.
    const isPlaying = args.state === 1;
    emit('isPlayingChanged', isPlaying);
  });

  let playerReadyTimeout;
  api.playerReady.on(() => {
    // Debounce playerReady to prevent multiple fires
    clearTimeout(playerReadyTimeout);
    playerReadyTimeout = setTimeout(() => {
        // console.log('Player ready');
        PracticeEngine.attachScore(api); 
        emit('playerReady', api);
    }, 50);
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
  
  // Determine the actual AlphaTab note object
  // PracticeEngine passes the raw AlphaTab note object as 'noteRef'
  // But sometimes it might be wrapped.
  const noteObj = note.ref ? note.ref : note;

  // Validate it's an object (simple check)
  if (!noteObj || typeof noteObj !== 'object') {
     // console.warn("Invalid note object for marking", note);
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

      // Trigger re-render with batching
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

onMounted(() => {
  console.log("ScoreViewer Mounted");
  initAlphaTab();
});

onUnmounted(() => {
  console.log("ScoreViewer Unmounted");
  if (api) {
        try {
            api.destroy();
        } catch (e) {
            console.warn("Error destroying AlphaTab:", e);
        }
        api = null;
    }
});

// ...

// Expose methods
const playPause = () => {
  if (!api || !api.player) return;
  
  try {
      // Check audio context state if possible (though AlphaTab hides it mostly)
      // Just wrap in try-catch to be safe
      api.playPause();
  } catch (e) {
      console.warn("Play/Pause error:", e);
  }
};

const stop = () => {
    if (!api || !api.player) return;
    try {
        api.pause();
        api.tickPosition = 0; 
    } catch (e) {
        console.warn("Error stopping player:", e);
    }
};

const clear = () => {
    if (api) {
        try {
            api.destroy();
        } catch (e) {
            console.warn("Error destroying API:", e);
        }
        api = null;
    }
    if (scoreContainer.value) {
        scoreContainer.value.innerHTML = '';
    }
    markers.value = [];
};

const getApi = () => api;
// ...
const loadFile = (file) => {
  if (!api) return;
  
  // Stop player before loading new file to avoid conflicts
  try {
      api.pause();
  } catch(e) {}
  
  const reader = new FileReader();
  reader.onload = (e) => {
    if (e.target?.result) {
      if (api) {
          api.load(e.target.result);
      } else {
          // If api is not ready (which shouldn't happen if loaded), queue or init?
          // Actually, if we are invisible, api might not be created yet.
          // But loadFile is called when we select a file.
          // If we are in empty state, ScoreViewer is v-show="false" (or true now).
          // Wait, Home.vue uses v-show. So element exists but display:none?
          // v-show="isScoreLoaded" -> if false, display:none.
          // So dimensions are 0.
          
          // We need to ensure we don't init AlphaTab until visible.
          // But loadFile is what triggers isScoreLoaded=true in Home.vue (eventually).
          
          // Actually, Home.vue handles file loading, then sets isScoreLoaded=true.
          // Then ScoreViewer becomes visible.
          // Then we should init/load.
          
          // Let's defer loading until we have dimensions.
          pendingLoadData = e.target.result;
          checkVisibilityAndInit();
      }
    }
  };
  reader.readAsArrayBuffer(file);
};

let pendingLoadData = null;
let resizeObserver = null;

const checkVisibilityAndInit = () => {
    if (!scoreContainer.value) return;
    
    // Check if visible and has width
    const rect = scoreContainer.value.getBoundingClientRect();
    
    // Strict check: if width is 0, we are invisible (e.g. display:none from v-show)
    if (rect.width === 0 || rect.height === 0) {
        // console.log("Skipping AlphaTab init - container invisible");
        return;
    }

    if (!api) {
        initAlphaTab();
    }
    
    if (api && pendingLoadData) {
        try {
            api.load(pendingLoadData);
            pendingLoadData = null;
        } catch (e) {
            console.error("Error loading pending data", e);
        }
    }
};

onMounted(() => {
  console.log("ScoreViewer Mounted");
  
  // Use ResizeObserver to detect when we become visible/resized
  resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
           // Only trigger if we have dimensions
          if (entry.contentRect.width > 0 && entry.contentRect.height > 0) {
              checkVisibilityAndInit();
          }
      }
  });
  
  if (scoreContainer.value) {
      resizeObserver.observe(scoreContainer.value);
  }
  
  // Try init immediately if already visible
  checkVisibilityAndInit();
});

onUnmounted(() => {
  console.log("ScoreViewer Unmounted");
  if (resizeObserver) {
      resizeObserver.disconnect();
      resizeObserver = null;
  }
  if (api) {
        try {
            api.destroy();
        } catch (e) {
            console.warn("Error destroying AlphaTab:", e);
        }
        api = null;
    }
});


watch(
  () => props.fileUrl,
  (newUrl) => {
    if (newUrl) {
      console.log("Loading new file from watch:", newUrl);
      if (api) {
        try {
          api.pause();
        } catch (e) {
          // Ignore parsing errors or if user wasn't playing
        }
        api.load(newUrl);
      } else {
        pendingLoadData = newUrl;
        checkVisibilityAndInit();
      }
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

watch(soundFontUrl, (newUrl) => {
  if (api && newUrl) {
    console.log("Updating SoundFont URL to:", newUrl);
    api.settings.player.soundFont = newUrl;
    api.updateSettings();
  }
});

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
  clear,
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
