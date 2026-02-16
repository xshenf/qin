<script setup>
import { ref, nextTick } from 'vue';
import ScoreViewer from './components/ScoreViewer.vue';
import AudioEngine from './audio/AudioEngine';
import PracticeEngine from './engine/PracticeEngine';

const scoreViewer = ref(null);
const isMicActive = ref(false);
const detectedPitch = ref('--');
const detectedNote = ref('--');
const isPlaying = ref(false);

// 配置选项
const staveProfile = ref('default'); // default, score, tab
const zoom = ref(100); // 50-200%
const playbackSpeed = ref(100); // 50-200%
const layoutWidth = ref('fit'); // fit, full

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
      alert("麦克风访问失败: " + e.message);
    }
  }
};

const handleFileSelect = (event) => {
  const file = event.target.files[0];
  if (file && scoreViewer.value) {
    scoreViewer.value.loadFile(file);
  }
};

const togglePlayback = () => {
  if (scoreViewer.value) {
    scoreViewer.value.playPause();
    isPlaying.value = !isPlaying.value;
  }
};

const handleScoreReady = (api) => {
  console.log("Score loaded!", api);
  PracticeEngine.attachScore(api);
  applySettings(); // 应用初始设置
};

// 应用设置到 AlphaTab API
const applySettings = () => {
  const api = scoreViewer.value?.getApi();
  if (!api) return;

  // 谱面类型映射
  const staveProfileMap = {
    'default': 0, // Default (Score + Tab)
    'score': 2,   // Score only
    'tab': 3      // Tab only
  };

  // 应用设置
  api.settings.display.staveProfile = staveProfileMap[staveProfile.value] || 0;
  api.settings.display.scale = zoom.value / 100;
  api.playbackSpeed = playbackSpeed.value / 100;
  
  // 始终使用 Page 模式（垂直分页），宽度通过 CSS 控制
  api.settings.display.layoutMode = 0; // Page

  // 更新设置并重新渲染
  api.updateSettings();
  nextTick(() => {
    api.render();
  });
};

// 监听配置变化
const onStaveProfileChange = () => applySettings();
const onZoomChange = () => applySettings();
const onSpeedChange = () => applySettings();
const onWidthChange = () => applySettings();

const demoFile = 'https://www.alphatab.net/files/canon.gp'; 
</script>

<template>
  <div class="app-container">
    <header>
      <div class="header-left">
        <h1>🎸 Guitar Practice</h1>
      </div>

      <div class="toolbar">
        <!-- 文件加载 -->
        <div class="tool-group">
          <label class="file-btn">
            📂 加载
            <input type="file" accept=".gp,.gp3,.gp4,.gp5,.gpx,.gp7" @change="handleFileSelect" hidden />
          </label>
        </div>

        <!-- 播放控制 -->
        <div class="tool-group">
          <button @click="togglePlayback" :class="{ active: isPlaying }">
            {{ isPlaying ? '⏸ 暂停' : '▶ 播放' }}
          </button>
        </div>

        <!-- 谱面类型 -->
        <div class="tool-group">
          <label class="control-label">谱面</label>
          <select v-model="staveProfile" @change="onStaveProfileChange" class="compact-select">
            <option value="default">混合</option>
            <option value="score">五线谱</option>
            <option value="tab">六线谱</option>
          </select>
        </div>

        <!-- 缩放 -->
        <div class="tool-group">
          <label class="control-label">缩放</label>
          <select v-model.number="zoom" @change="onZoomChange" class="compact-select">
            <option :value="50">50%</option>
            <option :value="75">75%</option>
            <option :value="100">100%</option>
            <option :value="125">125%</option>
            <option :value="150">150%</option>
            <option :value="200">200%</option>
          </select>
        </div>

        <!-- 播放速度 -->
        <div class="tool-group">
          <label class="control-label">速度</label>
          <select v-model.number="playbackSpeed" @change="onSpeedChange" class="compact-select">
            <option :value="50">50%</option>
            <option :value="75">75%</option>
            <option :value="100">100%</option>
            <option :value="125">125%</option>
            <option :value="150">150%</option>
          </select>
        </div>

        <!-- 宽度模式 -->
        <div class="tool-group">
          <label class="control-label">宽度</label>
          <select v-model="layoutWidth" @change="onWidthChange" class="compact-select">
            <option value="fit">适应</option>
            <option value="full">撑满</option>
          </select>
        </div>

        <!-- 麦克风 -->
        <div class="tool-group">
          <button @click="toggleMic" :class="{ active: isMicActive }" class="mic-btn">
            {{ isMicActive ? '🎤 ON' : '🎤 OFF' }}
          </button>
          <div class="monitor" v-if="isMicActive">
            <div class="monitor-item">
              <span class="label">音高</span>
              <span class="value">{{ detectedNote }}</span>
            </div>
          </div>
        </div>
      </div>
    </header>

    <main :class="'layout-' + layoutWidth">
      <ScoreViewer 
        ref="scoreViewer" 
        :file-url="demoFile"
        @playerReady="handleScoreReady"
      />
    </main>
  </div>
</template>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100%;
  padding: 0;
  margin: 0;
  background: #1a1a2e;
  color: #e0e0e0;
  overflow-x: hidden;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(135deg, #16213e 0%, #1a1a2e 100%);
  padding: 10px 20px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.4);
  z-index: 10;
  border-bottom: 1px solid #2a2a4a;
  flex-shrink: 0;
}

.header-left h1 {
  font-size: 1rem;
  margin: 0;
  color: #42b883;
  white-space: nowrap;
}

.toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
}

.tool-group {
  display: flex;
  gap: 4px;
  align-items: center;
  padding: 0 6px;
  border-right: 1px solid #333355;
}

.tool-group:last-child {
  border-right: none;
}

.control-label {
  font-size: 0.75rem;
  color: #888;
  white-space: nowrap;
}

.compact-select {
  padding: 4px 8px;
  background: #2a2a4a;
  color: #e0e0e0;
  border: 1px solid #3a3a5a;
  border-radius: 4px;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s;
}

.compact-select:hover {
  border-color: #42b883;
}

.file-btn {
  padding: 5px 12px;
  background: #2a2a4a;
  color: #e0e0e0;
  border: 1px solid #3a3a5a;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
  transition: all 0.2s;
}

.file-btn:hover {
  background: #3a3a5a;
  border-color: #42b883;
}

button {
  padding: 5px 12px;
  background: #2a2a4a;
  color: #e0e0e0;
  border: 1px solid #3a3a5a;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 0.8rem;
}

button:hover {
  background: #3a3a5a;
  border-color: #42b883;
}

button.active {
  background: #42b883;
  color: #1a1a2e;
  border-color: #42b883;
}

button.mic-btn.active {
  background: #e74c3c;
  border-color: #c0392b;
  color: white;
}

.monitor {
  display: flex;
  gap: 8px;
  background: #111122;
  padding: 3px 10px;
  border-radius: 4px;
  border: 1px solid #333355;
}

.monitor-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.monitor-item .label {
  font-size: 0.6rem;
  color: #666;
}

.monitor-item .value {
  font-family: monospace;
  font-size: 0.85rem;
  color: #42b883;
  font-weight: 600;
}

main {
  flex: 1;
  overflow-x: hidden;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  width: 100%;
}

/* 宽度模式 - 只控制 main 容器，AlphaTab 会自动适应 */
main.layout-fit {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
  box-sizing: border-box;
}

main.layout-full {
  max-width: none;
  margin: 0;
  padding: 0;
}

/* 强制移除撑满模式下的所有 margin 和 padding */
main.layout-full :deep(*) {
  margin: 0 !important;
  padding: 0 !important;
}

main.layout-full :deep(.score-wrapper),
main.layout-full :deep(.score-container) {
  width: 100% !important;
  max-width: 100% !important;
}
</style>
