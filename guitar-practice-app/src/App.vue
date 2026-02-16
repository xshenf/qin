<script setup>
import { ref, nextTick } from 'vue';
import ScoreViewer from './components/ScoreViewer.vue';
import Tuner from './components/Tuner.vue';
import AudioEngine from './audio/AudioEngine';
import PracticeEngine from './engine/PracticeEngine';

const scoreViewer = ref(null);
const isMicActive = ref(false);
const detectedPitch = ref('--');
const detectedNote = ref('--');
const detectedFrequency = ref(null);
const isPlaying = ref(false);

// 调音器状态
const showTuner = ref(false);

// 全屏状态
const isFullscreen = ref(false);

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
          detectedFrequency.value = pitch.frequency; // 保存数值用于调音器
        } else {
          detectedPitch.value = '--';
          detectedNote.value = '--';
          detectedFrequency.value = null;
        }
      }, 100);
    } catch (e) {
      alert("麦克风访问失败: " + e.message);
    }
  }
};

const toggleTuner = () => {
  showTuner.value = !showTuner.value;
  // 打开调音器时自动开启麦克风
  if (showTuner.value && !isMicActive.value) {
    toggleMic();
  }
};

// 全屏切换
const toggleFullscreen = async () => {
  try {
    if (!document.fullscreenElement) {
      // 进入全屏
      await document.documentElement.requestFullscreen();
      isFullscreen.value = true;
      
      // 尝试锁定为横屏（可选，部分浏览器支持）
      if (screen.orientation && screen.orientation.lock) {
        try {
          await screen.orientation.lock('landscape');
        } catch (e) {
          console.log('横屏锁定不支持:', e);
        }
      }
    } else {
      // 退出全屏
      await document.exitFullscreen();
      isFullscreen.value = false;
      
      // 解锁屏幕方向
      if (screen.orientation && screen.orientation.unlock) {
        screen.orientation.unlock();
      }
    }
  } catch (e) {
    console.error('全屏切换失败:', e);
  }
};

// 监听全屏变化（用户按ESC退出时同步状态）
document.addEventListener('fullscreenchange', () => {
  isFullscreen.value = !!document.fullscreenElement;
});

const handleFileSelect = (event) => {
  const file = event.target.files[0];
  if (file && scoreViewer.value) {
    scoreViewer.value.loadFile(file);
  }
};

// 拖放功能
const isDragging = ref(false);

const handleDragOver = (e) => {
  e.preventDefault();
  e.stopPropagation();
  isDragging.value = true;
};

const handleDragLeave = (e) => {
  e.preventDefault();
  e.stopPropagation();
  isDragging.value = false;
};

const handleDrop = (e) => {
  e.preventDefault();
  e.stopPropagation();
  isDragging.value = false;
  
  const files = e.dataTransfer.files;
  if (files.length > 0) {
    const file = files[0];
    // 检查文件扩展名
    const validExtensions = ['.gp', '.gp3', '.gp4', '.gp5', '.gpx', '.gp7'];
    const fileName = file.name.toLowerCase();
    const isValid = validExtensions.some(ext => fileName.endsWith(ext));
    
    if (isValid && scoreViewer.value) {
      // 重置播放状态
      if (isPlaying.value) {
        scoreViewer.value.stop();
        isPlaying.value = false;
      }
      // 加载新文件
      scoreViewer.value.loadFile(file);
    } else {
      alert('请拖入有效的 Guitar Pro 文件 (.gp, .gp3, .gp4, .gp5, .gpx, .gp7)');
    }
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
  <div 
    class="app-container"
    @dragover="handleDragOver"
    @dragleave="handleDragLeave"
    @drop="handleDrop"
  >
    <!-- 拖放提示覆盖层 -->
    <div v-if="isDragging" class="drag-overlay">
      <div class="drag-hint">
        <div class="drag-icon">📂</div>
        <div class="drag-text">拖放 Guitar Pro 文件到此处</div>
      </div>
    </div>

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

        <!-- 全屏 -->
        <div class="tool-group">
          <button @click="toggleFullscreen" :class="{ active: isFullscreen }" title="全屏 / 横屏">
            {{ isFullscreen ? '🔳' : '⛶' }}
          </button>
        </div>

        <!-- 麦克风 -->
        <div class="tool-group">
          <button @click="toggleMic" :class="{ active: isMicActive }" class="mic-btn">
            {{ isMicActive ? '🎤 ON' : '🎤 OFF' }}
          </button>
          <button @click="toggleTuner" :class="{ active: showTuner }" title="调音器">
            🎵
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

    <!-- 调音器面板 -->
    <Tuner 
      :is-active="showTuner"
      :detected-note="detectedNote"
      :detected-pitch="detectedFrequency"
      @close="showTuner = false"
    />
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

/* 撑满模式 - 精确控制特定元素而非所有元素 */
main.layout-full :deep(.score-wrapper) {
  width: 100% !important;
  max-width: 100% !important;
  margin: 0 !important;
}

main.layout-full :deep(.score-container) {
  width: 100% !important;
  max-width: 100% !important;
  margin: 0 !important;
}

/* 拖放覆盖层 */
.drag-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(26, 26, 46, 0.95);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.drag-hint {
  text-align: center;
  color: #42b883;
  animation: pulse 1.5s ease-in-out infinite;
}

.drag-icon {
  font-size: 5rem;
  margin-bottom: 20px;
}

.drag-text {
  font-size: 1.5rem;
  font-weight: 600;
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.05);
    opacity: 0.8;
  }
}

/* 移动端适配 */
@media (max-width: 768px) {
  header {
    flex-direction: column;
    padding: 8px 10px;
    gap: 8px;
  }

  .header-left h1 {
    font-size: 0.9rem;
  }

  .toolbar {
    width: 100%;
    flex-wrap: wrap;
    gap: 6px;
    justify-content: space-between;
  }

  .tool-group {
    padding: 0 4px;
    border-right: none;
  }

  .control-label {
    display: none; /* 隐藏标签节省空间 */
  }

  .compact-select {
    font-size: 0.75rem;
    padding: 4px 6px;
  }

  button {
    font-size: 0.75rem;
    padding: 6px 10px;
    min-width: 44px; /* 确保触摸目标足够大 */
    min-height: 44px;
  }

  .file-btn {
    font-size: 0.75rem;
    padding: 6px 10px;
  }

  .monitor {
    padding: 2px 8px;
  }

  .monitor-item .label {
    font-size: 0.55rem;
  }

  .monitor-item .value {
    font-size: 0.75rem;
  }

  /* 调音器在移动端全屏显示 */
  .tuner-panel {
    width: 95vw;
    min-width: unset;
    max-width: 500px;
    padding: 15px;
  }

  .tuner-header h3 {
    font-size: 1rem;
  }

  .strings {
    grid-template-columns: repeat(3, 1fr); /* 移动端分2行显示 */
  }

  .detected-pitch {
    padding: 10px;
  }

  .pitch-note {
    font-size: 2rem;
  }
}

@media (max-width: 480px) {
  .header-left h1 {
    font-size: 0.8rem;
  }

  button, .file-btn {
    padding: 8px;
    font-size: 0.7rem;
  }

  .compact-select {
    font-size: 0.7rem;
    padding: 4px;
  }

  /* 更紧凑的工具栏 */
  .toolbar {
    gap: 4px;
  }

  .tool-group {
    flex: 1;
    min-width: fit-content;
  }
}

/* 横屏优化 */
@media (orientation: landscape) and (max-height: 600px) {
  header {
    padding: 4px 10px;
  }

  .header-left h1 {
    font-size: 0.8rem;
  }

  button {
    padding: 4px 8px;
    min-height: 36px;
  }

  .toolbar {
    gap: 4px;
  }
}

/* 全屏模式优化 */
.app-container:fullscreen {
  background: white;
}

.app-container:fullscreen header {
  background: rgba(22, 33, 62, 0.95);
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  backdrop-filter: blur(10px);
}

.app-container:fullscreen main {
  padding-top: 60px;
}

/* 全屏横屏模式 - 最大化乐谱显示 */
@media (orientation: landscape) {
  .app-container:fullscreen header {
    padding: 2px 10px;
  }

  .app-container:fullscreen .header-left h1 {
    font-size: 0.7rem;
  }

  .app-container:fullscreen button {
    font-size: 0.7rem;
    padding: 3px 6px;
    min-height: 32px;
  }

  .app-container:fullscreen main {
    padding-top: 45px;
  }
}
</style>
