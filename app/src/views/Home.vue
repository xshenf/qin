<script setup>
import { ref, nextTick, watch, onMounted, onUnmounted } from 'vue';
import ScoreViewer from '../components/ScoreViewer.vue';
import Tuner from '../components/Tuner.vue';
import AudioEngine from '../audio/AudioEngine';
import PracticeEngine from '../engine/PracticeEngine';
import PerformanceBar from '../components/PerformanceBar.vue';
import { saveScore, getScoresList, getScoreData, deleteScore } from '../utils/db';
import { syncHistoryToBackend, fetchHistoryFromBackend, fetchScoreDataFromBackend } from '../utils/api';
import { useAuthStore } from '../stores/auth';
import { useRouter } from 'vue-router';
// import defaultScoreWithUrl from '../assets/gtp/Canon_D.gp5?url'; 

const scoreViewer = ref(null);
const isMicActive = ref(false);
const detectedPitch = ref('--');
const detectedNote = ref('--');
const detectedFrequency = ref(null);
const detectedPitchObj = ref(null); // For PerformanceBar
const isPlaying = ref(false);

// 调音器状态
const showTuner = ref(false);

// 全屏状态
const isFullscreen = ref(false);

// 录音状态
const isRecording = ref(false);
const recordingTime = ref(0);
const recordedAudioUrl = ref(null); // 录音的 blob URL
const isPlayingRecording = ref(false); // 是否正在播放录音
let mediaRecorder = null;
let recordedChunks = [];
let recordingTimer = null;
let audioPlayer = null; // 音频播放器

// 配置选项
const staveProfile = ref('default'); // default, score, tab
const zoom = ref(100); // 50-200%
const playbackSpeed = ref(100); // 50-200%

// 自动检测移动端，默认开启低音增强
const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
const bassBoost = ref(isMobile);
const showToolbar = ref(!isMobile);

// 练习模式状态
const isPracticeMode = ref(false);
const tempoFeedback = ref('--');
const feedbackColor = ref('#888');

// 乐器（轨道）选择
const tracks = ref([]);
const selectedTrackIndex = ref(0);

let uiInterval = null;

const togglePractice = () => {
  isPracticeMode.value = !isPracticeMode.value;
  if (isPracticeMode.value) {
    // Connect pitch callback for PerformanceBar
    PracticeEngine.setPitchCallback((data) => {
        detectedPitchObj.value = data;
    });
    
    PracticeEngine.start();
  } else {
    PracticeEngine.stop();
    detectedPitchObj.value = null; // Clear bar
    tempoFeedback.value = '--';
  }
};

// 监听低音增强变化，如果麦克风开启中则重启
watch(bassBoost, async (newValue) => {
  if (isMicActive.value) {
    await toggleMic(); // 关闭
    await toggleMic(); // 重新开启（会应用新配置）
  }
});
// 监听状态自动开关麦克风
watch([isPracticeMode, showTuner], ([practice, tuner]) => {
  const shouldActive = practice || tuner;
  if (shouldActive && !isMicActive.value) {
    toggleMic();
  } else if (!shouldActive && isMicActive.value) {
    toggleMic();
  }
});

const toggleMic = async () => {
  if (isMicActive.value) {
    await AudioEngine.stopMicrophone(); // 确保等待资源释放
    isMicActive.value = false;
    clearInterval(uiInterval);
    // 清除音高保持
    detectedPitch.value = '--';
    detectedNote.value = '--';
    detectedFrequency.value = null;
  } else {
    try {
      // 传入低音增强配置
      await AudioEngine.startMicrophone({ bassBoost: bassBoost.value });
      isMicActive.value = true;
      
      let lastDetectedTime = 0;
      let lastPitch = null;
      
      uiInterval = setInterval(() => {
        const pitch = AudioEngine.getPitch();
        const now = Date.now();
        
        if (pitch) {
          // 检测到新音高，立即更新
          detectedPitch.value = pitch.frequency.toFixed(1) + ' Hz';
          detectedNote.value = pitch.note;
          detectedFrequency.value = pitch.frequency;
          lastDetectedTime = now;
          lastPitch = pitch;
        } else if (lastPitch && (now - lastDetectedTime < 500)) {
          // 没检测到但在500ms内，保持上次的音高（余音效果）
          detectedPitch.value = lastPitch.frequency.toFixed(1) + ' Hz';
          detectedNote.value = lastPitch.note;
          detectedFrequency.value = lastPitch.frequency;
        } else {
          // 超过500ms没检测到，清除显示
          detectedPitch.value = '--';
          detectedNote.value = '--';
          detectedFrequency.value = null;
          lastPitch = null;
        }
      }, 100);
    } catch (e) {
      alert("麦克风访问失败: " + e.message);
    }
  }
};

const toggleTuner = () => {
  showTuner.value = !showTuner.value;
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

// 录音功能
const toggleRecording = async () => {
  if (!isRecording.value) {
    // 开始录音
    try {
      // 音频约束 - 启用降噪和优化
      const constraints = {
        audio: {
          echoCancellation: true,      // 回声消除
          noiseSuppression: true,       // 噪音抑制
          autoGainControl: true,        // 自动增益控制
          sampleRate: 44100,            // 采样率
          channelCount: 1               // 单声道（减小文件大小）
        },
        video: false
      };

      // 获取音频流
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      
      // 创建 MediaRecorder
      mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      });
      
      recordedChunks = [];
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          recordedChunks.push(event.data);
        }
      };
      
      mediaRecorder.onstop = () => {
        // 停止所有音频轨道
        stream.getTracks().forEach(track => track.stop());
      };
      
      mediaRecorder.start();
      isRecording.value = true;
      recordingTime.value = 0;
      
      // 启动计时器
      recordingTimer = setInterval(() => {
        recordingTime.value++;
      }, 1000);
      
    } catch (e) {
      alert('录音启动失败: ' + e.message);
      console.error('录音失败:', e);
    }
  } else {
    // 停止录音
    stopRecording();
  }
};

const stopRecording = () => {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
    isRecording.value = false;
    clearInterval(recordingTimer);
    
    // 创建录音 blob 和 URL
    setTimeout(() => {
      if (recordedChunks.length > 0) {
        const blob = new Blob(recordedChunks, { type: 'audio/webm' });
        // 清理之前的 URL
        if (recordedAudioUrl.value) {
          URL.revokeObjectURL(recordedAudioUrl.value);
        }
        recordedAudioUrl.value = URL.createObjectURL(blob);
      }
    }, 100);
  }
};

const saveRecording = () => {
  if (recordedChunks.length === 0) {
    alert('没有录音数据');
    return;
  }
  
  const blob = new Blob(recordedChunks, { type: 'audio/webm' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `guitar-recording-${new Date().getTime()}.webm`;
  a.click();
  URL.revokeObjectURL(url);
};

const checkMicStatus = () => {
    // 恢复麦克风状态（如果应该开启且当前未开启）
    if ((isPracticeMode.value || showTuner.value) && !isMicActive.value) {
        toggleMic();
    }
};

// 播放/暂停录音
const togglePlayRecording = async () => {
  if (!recordedAudioUrl.value) return;
  
  // 播放前先停止麦克风，防止手机音频路由到听筒（通话模式）导致声音小
  if (isMicActive.value) {
    await toggleMic();
  }
  
  if (!audioPlayer) {
    // 创建音频播放器
    audioPlayer = new Audio(recordedAudioUrl.value);
    audioPlayer.addEventListener('ended', () => {
      isPlayingRecording.value = false;
      checkMicStatus();
    });
  }
  
  if (isPlayingRecording.value) {
    audioPlayer.pause();
    isPlayingRecording.value = false;
    checkMicStatus();
  } else {
    try {
      await audioPlayer.play();
      isPlayingRecording.value = true;
    } catch (e) {
      alert('播放失败: ' + e.message);
    }
  }
};

// 停止播放录音
const stopPlayRecording = () => {
  if (audioPlayer) {
    audioPlayer.pause();
    audioPlayer.currentTime = 0;
    isPlayingRecording.value = false;
    checkMicStatus();
  }
};

// 清除录音
const clearRecording = () => {
  stopPlayRecording();
  if (recordedAudioUrl.value) {
    URL.revokeObjectURL(recordedAudioUrl.value);
    recordedAudioUrl.value = null;
  }
  if (audioPlayer) {
    audioPlayer = null;
  }
  recordedChunks = [];
  recordingTime.value = 0;
};

// 格式化录音时长
const formatRecordingTime = (seconds) => {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
};

const loadFileAndSave = async (file) => {
  if (scoreViewer.value) {
    isScoreLoaded.value = false;
    scoreViewer.value.loadFile(file);
    try {
      await saveScore(file.name, file.name, file);
      await loadHistory(file.name);
    } catch (e) {
      console.error("Failed to save score to history", e);
    }
  }
};

const handleFileSelect = (event) => {
  const file = event.target.files[0];
  if (file && scoreViewer.value) {
    loadFileAndSave(file);
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
    const validExtensions = ['.gp', '.gp3', '.gp4', '.gp5', '.gpx', '.gp7', '.gtp', '.gp8'];
    const fileName = file.name.toLowerCase();
    const isValid = validExtensions.some(ext => fileName.endsWith(ext));
    
    if (isValid && scoreViewer.value) {
      // 重置播放状态
      if (isPlaying.value) {
        scoreViewer.value.stop();
        isPlaying.value = false;
      }
      loadFileAndSave(file);
    } else {
      alert('请拖入有效的 Guitar Pro 文件 (.gp, .gp3, .gp4, .gp5, .gpx, .gp7)');
    }
  }
};

const togglePlayback = () => {
  if (!isScoreLoaded.value) return;
  if (scoreViewer.value) {
    scoreViewer.value.playPause();
    // Do not toggle isPlaying here manually, wait for event from component
  }
};

const handleScoreReady = (api) => {
  console.log("Score loaded!", api);
  PracticeEngine.attachScore(api);
  
  // 设置练习回调
  PracticeEngine.setResultCallback((result) => {
    // 标记音符
    if (scoreViewer.value) {
      scoreViewer.value.markNote(result.noteRef, result.type);
    }
    
    // 更新速度提示
    if (result.type === 'hit') {
      const textMap = { perfect: '准确', early: '抢拍', late: '拖拍' };
      const colorMap = { perfect: '#42b883', early: '#f39c12', late: '#f39c12' };
      tempoFeedback.value = textMap[result.timing];
      feedbackColor.value = colorMap[result.timing];
      
      // 1.5秒后重置
      setTimeout(() => {
        tempoFeedback.value = '--';
        feedbackColor.value = '#888';
      }, 1500);
    } else {
        // Miss logic?
    }
  });
  

  
  // 初始化轨道列表
  if (api.score && api.score.tracks.length > 0) {
    tracks.value = api.score.tracks.map((t, i) => ({
      index: i,
      name: t.name || `Instrument ${i + 1}`,
      instrument: t
    }));
    // 默认选中第一轨（通常是主旋律或吉他1）
    selectedTrackIndex.value = 0;
  } else {
    tracks.value = [];
  }
};

// 监听轨道切换
const onTrackChange = () => {
    if (scoreViewer.value) {
        scoreViewer.value.renderTrack(selectedTrackIndex.value);
    }
};



const demoFile = ref(null);
const isScoreLoaded = ref(false);
const scoreHistory = ref([]);

const authStore = useAuthStore();
const router = useRouter();

const handleLoginToggle = async () => {
  if (authStore.isAuthenticated) {
    if (confirm("确定要退出登录吗？")) {
      authStore.logout();
      loadHistory();
    }
  } else {
    router.push('/login');
  }
};

const loadHistory = async (syncDataId = null) => {
  try {
    let localHistory = await getScoresList();
    if (authStore.isAuthenticated) {
      const backendHistory = await fetchHistoryFromBackend();
      const localMap = new Map();
      localHistory.forEach(item => localMap.set(item.id, item));
      
      for (const bItem of backendHistory) {
        const id = bItem.local_id || bItem.id;
        const existing = localMap.get(id);
        // If it's new, or the backend version has a newer addTime, update local stub
        if (!existing || bItem.addTime > existing.addTime) {
           localMap.set(id, { id: id, name: bItem.name, addTime: bItem.addTime });
           
           let existingData = null;
           if (existing) {
             const fullItem = await getScoreData(id);
             if (fullItem) existingData = fullItem.data;
           }
           await saveScore(id, bItem.name, existingData, bItem.addTime);
        }
      }
      
      scoreHistory.value = Array.from(localMap.values()).sort((a, b) => b.addTime - a.addTime);
      syncHistoryToBackend(scoreHistory.value, syncDataId).catch(console.error);
    } else {
      scoreHistory.value = localHistory;
    }
  } catch (e) {
    console.error("Failed to load score history", e);
  }
};

const loadFromHistory = async (id) => {
  try {
    const item = await getScoreData(id);
    
    // 如果本地只有壳数据没有 Blob 数据（即从云端同步过来的新设备），则去云端拉取 Blob
    if (item && !item.data && authStore.isAuthenticated) {
      const blob = await fetchScoreDataFromBackend(id);
      if (blob) {
        item.data = blob;
        // 把拉取到的数据保存入本地补全
        await saveScore(item.id, item.name, item.data, item.addTime);
      } else {
        throw new Error("同步该谱子数据失败，可能在云端已损坏或不存在");
      }
    }

    if (item && item.data) {
      if (scoreViewer.value) {
        isScoreLoaded.value = false;
        if (isPlaying.value) {
          scoreViewer.value.stop();
          isPlaying.value = false;
        }
        scoreViewer.value.loadFile(item.data);
        
        // 更新历史记录时间使其排到最前面, 不上传原来的数据
        saveScore(item.id, item.name, item.data).then(() => {
          loadHistory();
        }).catch(err => console.error("Update history time failed", err));
      }
    }
  } catch (e) {
    alert("无法加载历史乐谱: " + e.message);
  }
};

const removeHistoryItem = async (id, e) => {
  e.stopPropagation();
  try {
    await deleteScore(id);
    await loadHistory();
  } catch(e) {
    console.error("Error deleting history", e);
  }
};

const handleScoreLoaded = (score) => {
    console.log("Score loaded:", score);
    isScoreLoaded.value = true;
};

const closeScore = () => {
    console.log("Closing score");
    isScoreLoaded.value = false;
    isPlaying.value = false;
    tracks.value = [];
    
    // Reset detection display
    detectedPitch.value = '--';
    detectedNote.value = '--';
    
    if (scoreViewer.value) {
        scoreViewer.value.stop();
        scoreViewer.value.clear();
    }
    PracticeEngine.stop();
    
    // Clean up current Demo file reference if any
    demoFile.value = null;
    
    // Reset file input if possible (not easily accessible via ref here but handleFileSelect handles new ones)
};
// console.log("Default Score URL:", demoFile.value);
// 键盘快捷键
const handleKeydown = (e) => {
  // 如果是空格键 && 乐谱已加载 && 焦点不在输入框
  if ((e.code === 'Space' || e.key === ' ') && isScoreLoaded.value) {
    if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
    
    e.preventDefault(); // 防止网页滚动
    togglePlayback();
  }
};

onMounted(() => {
    window.addEventListener('keydown', handleKeydown);
    loadHistory();
});

onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown);
});
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
      <div class="header-bar">
        <div class="header-left" @click="closeScore" style="cursor: pointer;" title="返回首页">
          <img src="/qin-logo.svg" alt="Qin Logo" class="app-logo" />
        </div>
        
        <!-- 用户登录状态 -->
        <div class="user-status" style="margin-left: 10px; cursor: pointer;" @click="handleLoginToggle">
          <span v-if="authStore.isAuthenticated" style="color: #42b883; font-size: 0.9rem;" title="退出登录">
            👤 {{ authStore.user?.email || authStore.user?.username || '已登录' }}
          </span>
          <span v-else style="color: #888; font-size: 0.9rem;">
            登录/注册
          </span>
        </div>

        <div class="mobile-controls" v-if="isMobile">
           <button @click="togglePlayback" :class="{ active: isPlaying }" :disabled="!isScoreLoaded">
            {{ isPlaying ? '⏸' : '▶' }}
           </button>
           <button @click="showToolbar = !showToolbar" :class="{ active: showToolbar }">
             {{ showToolbar ? '🔼' : '🛠️' }}
           </button>
        </div>
      </div>

      <div class="toolbar" v-show="!isMobile || showToolbar">
        <!-- 文件加载 -->
        <div class="tool-group">
          <label class="file-btn">
            📂 加载
            <input type="file" accept=".gp,.gp3,.gp4,.gp5,.gpx,.gp7" @change="handleFileSelect" hidden />
          </label>
        </div>

        <!-- 播放控制 -->
        <div class="tool-group">
          <button @click="togglePlayback" :class="{ active: isPlaying }" :disabled="!isScoreLoaded">
            {{ isPlaying ? '⏸ 暂停' : '▶ 播放' }}
          </button>
        </div>

        <!-- 练习模式 -->
        <div class="tool-group">
          <button 
            @click="togglePractice" 
            class="tool-btn" 
            :class="{ active: isPracticeMode }"
            title="开启智能练习模式"
            :disabled="!isScoreLoaded"
          >
            {{ isPracticeMode ? '🎯 练习中' : '🎯 练习' }}
          </button>
          
          <div class="monitor" v-if="isPracticeMode">
             <div class="monitor-item">
               <span class="label">评价</span>
               <span class="value" :style="{ color: feedbackColor }">{{ tempoFeedback }}</span>
             </div>
          </div>
        </div>

        <!-- 乐器选择 -->
        <div class="tool-group" v-if="tracks.length > 1">
          <label class="control-label">乐器</label>
          <select v-model="selectedTrackIndex" @change="onTrackChange" class="compact-select" style="max-width: 120px;">
            <option v-for="track in tracks" :key="track.index" :value="track.index">
              {{ track.name }}
            </option>
          </select>
        </div>

        <!-- 谱面类型 -->
        <div class="tool-group">
          <label class="control-label">谱面</label>
          <select v-model="staveProfile" class="compact-select">
            <option value="default">混合</option>
            <option value="score">五线谱</option>
            <option value="tab">六线谱</option>
          </select>
        </div>

        <!-- 缩放 -->
        <div class="tool-group">
          <label class="control-label">缩放</label>
          <select v-model.number="zoom" class="compact-select">
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
          <select v-model.number="playbackSpeed" class="compact-select">
            <option :value="50">50%</option>
            <option :value="75">75%</option>
            <option :value="100">100%</option>
            <option :value="125">125%</option>
            <option :value="150">150%</option>
          </select>
        </div>


        <!-- 全屏 -->
        <div class="tool-group">
          <button @click="toggleFullscreen" :class="{ active: isFullscreen }" title="全屏 / 横屏">
            {{ isFullscreen ? '🔳' : '⛶' }}
          </button>
        </div>

        <!-- 调音器/麦克风组 -->
        <div class="tool-group">

          
          <!-- 低音增强开关 (仅在麦克风开启时显示，或者始终显示) -->
          <button 
            @click="bassBoost = !bassBoost" 
            class="tool-btn"
            :class="{ active: bassBoost }"
            title="开启低音增强（推荐手机端开启）"
          >
            {{ bassBoost ? '增强:开' : '增强:关' }}
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

        <!-- 录音 -->
        <div class="tool-group">
          <button @click="toggleRecording" :class="{ active: isRecording }" class="record-btn" title="录音">
            <span v-if="isRecording" class="recording-dot"></span>
            {{ isRecording ? '⏺ 停止' : '⏺ 录音' }}
          </button>
          <button 
            v-if="recordedAudioUrl && !isRecording" 
            @click="togglePlayRecording" 
            :class="{ active: isPlayingRecording }"
            title="播放录音"
          >
            {{ isPlayingRecording ? '⏸' : '▶️' }}
          </button>
          <button v-if="recordedAudioUrl && !isRecording" @click="saveRecording" title="保存录音">
            💾
          </button>
          <button v-if="recordedAudioUrl && !isRecording" @click="clearRecording" title="删除录音">
            🗑️
          </button>
          <div class="monitor" v-if="isRecording">
            <div class="monitor-item">
              <span class="label">时长</span>
              <span class="value">{{ formatRecordingTime(recordingTime) }}</span>
            </div>
          </div>
        </div>
      </div>
    </header>

    <PerformanceBar v-if="isPracticeMode" :detectedPitch="detectedPitchObj" />

    <main class="layout-full">
      <div v-if="!isScoreLoaded" class="empty-state">
        <div class="hero-section">
          <div class="hero-icon">🎸</div>
          <h2>没有加载乐谱</h2>
          <p>拖放GTP文件到此处，或者点击下方按钮打开</p>
          <label class="hero-btn">
            📂 打开乐谱文件
            <input type="file" accept=".gp,.gp3,.gp4,.gp5,.gpx,.gp7" @change="handleFileSelect" hidden />
          </label>
        </div>
        <div class="history-section" v-if="scoreHistory.length > 0">
          <div class="section-title">
            <h3>最近打开</h3>
          </div>
          <div class="history-list">
            <div 
              class="history-item" 
              v-for="item in scoreHistory" 
              :key="item.id"
              @click="loadFromHistory(item.id)"
            >
              <div class="item-icon">🎵</div>
              <div class="item-info">
                <div class="item-name">{{ item.name }}</div>
                <div class="item-time">{{ new Date(item.addTime).toLocaleString() }}</div>
              </div>
              <button class="delete-btn" @click="(e) => removeHistoryItem(item.id, e)" title="删除记录">×</button>
            </div>
          </div>
        </div>

        <div class="cards-grid" v-if="scoreHistory.length === 0">
          <div class="info-card">
            <div class="card-icon">📄</div>
            <h3>支持格式</h3>
            <p>支持所有主流GTP格式：.gp, .gp5, .gpx, .gp3, .gp4</p>
          </div>
          <div class="info-card">
            <div class="card-icon">🛠️</div>
            <h3>强大工具</h3>
            <p>内置调音器、录音机、以及智能练习模式，助你高效练琴</p>
          </div>
          <div class="info-card">
            <div class="card-icon">⚡</div>
            <h3>快捷操作</h3>
            <p>使用空格键播放/暂停，支持全屏模式和多种显示比例</p>
          </div>
        </div>
      </div>

      <ScoreViewer 
        class="score-viewer-layer"
        ref="scoreViewer" 
        :file-url="demoFile"
        :zoom="zoom"
        :stave-profile="staveProfile"
        :playback-speed="playbackSpeed"
        @playerReady="handleScoreReady"
        @playerFinished="isPlaying = false"
        @isPlayingChanged="(playing) => isPlaying = playing"
        @scoreLoaded="handleScoreLoaded"
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

.header-bar {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 20px;
}

.mobile-controls {
  display: flex;
  gap: 8px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: nowrap;
}

.header-left h1 {
  font-size: 1.2rem;
  margin: 0;
  color: #42b883;
  white-space: nowrap;
  font-weight: 700;
}

.app-logo {
  height: 32px;
  width: 32px;
  border-radius: 6px;
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

button.record-btn.active {
  background: #e74c3c;
  border-color: #c0392b;
  color: white;
  position: relative;
}

.recording-dot {
  position: absolute;
  top: 5px;
  right: 5px;
  width: 8px;
  height: 8px;
  background: #ff0000;
  border-radius: 50%;
  animation: recording-pulse 1.5s ease-in-out infinite;
}

@keyframes recording-pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.5;
    transform: scale(1.2);
  }
}

.monitor {
  display: flex;
  gap: 8px;
  align-items: center;
  background: rgba(0, 0, 0, 0.2);
  padding: 4px 10px;
  border-radius: 4px;
}

.monitor-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 45px; /* 固定最小宽度防止跳动 */
}

.monitor-item .label {
  font-size: 0.6rem;
  color: #888;
  line-height: 1;
}

.monitor-item .value {
  font-size: 0.9rem;
  font-weight: bold;
  color: #42b883;
  line-height: 1.2;
  font-family: monospace; /* 等宽字体防止数字跳动 */
  min-width: 40px; /* 确保值区域有足够空间 */
  text-align: center;
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
    align-items: stretch;
    padding: 8px 10px;
    gap: 8px;
  }

  .header-bar {
    justify-content: space-between;
    width: 100%;
  }

  .header-left h1 {
    font-size: 0.9rem;
  }

  .toolbar {
    width: 100%;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: flex-start;
  }

  .tool-group {
    padding: 0;
    border-right: none;
  }

  .control-label {
    display: none; /* 隐藏标签节省空间 */
  }

  .compact-select {
    font-size: 0.75rem;
    padding: 4px 6px;
    max-width: 90px;
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
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 44px;
    box-sizing: border-box;
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
    grid-template-columns: repeat(2, 1fr); /* 移动端分2列显示更合理 */
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
    padding: 6px 8px;
    font-size: 0.7rem;
    min-height: 38px;
  }

  .compact-select {
    font-size: 0.7rem;
    padding: 4px;
  }

  /* 更紧凑的工具栏 */
  .toolbar {
    gap: 6px;
  }

  .tool-group {
    flex: 1 1 auto;
    min-width: auto;
    display: flex;
    justify-content: center;
  }
  
  .tool-group > * {
    width: 100%;
    text-align: center;
  }

  .empty-state {
    padding: 20px;
  }
  
  .hero-section {
    margin-bottom: 30px;
  }
  
  .hero-icon {
    font-size: 3rem;
    margin-bottom: 10px;
  }
  
  .hero-section h2 {
    font-size: 1.5rem;
  }
  
  .hero-section p {
    font-size: 0.95rem;
    margin-bottom: 20px;
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

/* Empty State Styles */
.layout-full {
  flex: 1;
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.empty-state {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 10;
  display: flex;
  flex-direction: column;
  align-items: center;
  /* 用 flex-start + margin: auto 来替代 justify-content: center，防止溢出时顶部被截断 */
  justify-content: flex-start;
  padding: 40px;
  box-sizing: border-box;
  background: #1a1a2e;
  overflow-y: auto;
}

.score-viewer-layer {
  flex: 1;
  width: 100%;
  height: 100%;
}

.hero-section {
  text-align: center;
  margin-bottom: 60px;
  margin-top: auto; /* 配合 flex-start 垂直居中 */
}

.hero-icon {
  font-size: 4rem;
  margin-bottom: 20px;
}

.hero-section h2 {
  font-size: 2rem;
  margin: 0 0 10px;
  color: #42b883;
}

.hero-section p {
  color: #888;
  margin: 0 0 30px;
  font-size: 1.1rem;
}

.hero-btn {
  display: inline-block;
  padding: 12px 24px;
  background: #42b883;
  color: #1a1a2e;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.hero-btn:hover {
  background: #3aa876;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(66, 184, 131, 0.3);
}

.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
  width: 100%;
  max-width: 900px;
  margin-bottom: auto; /* 配合 flex-start 垂直居中 */
}

.info-card {
  background: #16213e;
  padding: 24px;
  border-radius: 12px;
  border: 1px solid #2a2a4a;
  text-align: center;
  transition: all 0.2s;
}

.info-card:hover {
  transform: translateY(-5px);
  border-color: #42b883;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.card-icon {
  font-size: 2rem;
  margin-bottom: 15px;
}

.info-card h3 {
  color: #e0e0e0;
  margin: 0 0 10px;
  font-size: 1.2rem;
}

.info-card p {
  color: #888;
  margin: 0;
  line-height: 1.5;
  font-size: 0.95rem;
}

/* History Section */
.history-section {
  width: 100%;
  max-width: 900px;
  margin-bottom: auto; /* 配合 flex-start 垂直居中 */
  background: #16213e;
  border-radius: 12px;
  border: 1px solid #2a2a4a;
  overflow: hidden;
}

.section-title {
  padding: 15px 20px;
  border-bottom: 1px solid #2a2a4a;
  background: rgba(0, 0, 0, 0.2);
}

.section-title h3 {
  margin: 0;
  color: #42b883;
  font-size: 1.1rem;
}

.history-list {
  max-height: 300px;
  overflow-y: auto;
}

.history-item {
  display: flex;
  align-items: center;
  padding: 15px 20px;
  border-bottom: 1px solid #2a2a4a;
  cursor: pointer;
  transition: background 0.2s;
}

.history-item:last-child {
  border-bottom: none;
}

.history-item:hover {
  background: rgba(66, 184, 131, 0.1);
}

.item-icon {
  font-size: 1.5rem;
  margin-right: 15px;
  opacity: 0.8;
}

.item-info {
  flex: 1;
  overflow: hidden;
}

.item-name {
  color: #e0e0e0;
  font-weight: 500;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-time {
  color: #888;
  font-size: 0.8rem;
}

.delete-btn {
  background: transparent;
  border: none;
  color: #888;
  font-size: 1.5rem;
  cursor: pointer;
  padding: 5px 10px;
  min-height: auto;
  min-width: auto;
  line-height: 1;
  opacity: 0;
  transition: all 0.2s;
}

.history-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  color: #e74c3c;
  transform: scale(1.1);
}

@media (max-width: 768px) {
  .hero-section {
    margin-bottom: 30px;
  }
  
  .history-section {
    margin-bottom: 20px;
  }
  
  .history-item {
    padding: 12px 15px;
  }
  
  .delete-btn {
    opacity: 1; /* 移动端始终显示删除按钮 */
    font-size: 1.2rem;
  }
}
</style>
