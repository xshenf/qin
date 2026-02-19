<template>
  <div class="tuner-panel" v-if="isActive">
    <div class="tuner-header">
      <h3>🎸 吉他调音器</h3>
      <div class="header-controls">
        <button @click="showPresets = !showPresets" class="text-btn" title="调音预设">📝 预设</button>
        <button @click="isEditing = !isEditing" class="text-btn" :class="{ active: isEditing }">
          {{ isEditing ? '完成' : '⚙️ 自定义' }}
        </button>
        <button @click="$emit('close')" class="close-btn">✕</button>
      </div>
    </div>

    <!-- 预设选择面板 -->
    <div class="presets-panel" v-if="showPresets">
      <div 
        v-for="preset in presets" 
        :key="preset.name" 
        class="preset-item"
        @click="applyPreset(preset.strings)"
      >
        {{ preset.name }}
      </div>
    </div>

    <div class="tuner-content">
      <!-- 标准音弦选择 -->
      <div class="strings">
        <div 
          v-for="(string, index) in guitarStrings" 
          :key="index"
          class="string-item"
          :class="{ active: !isEditing && isNearNote(string.note), editing: isEditing }"
        >
          <div class="string-name">{{ string.name }}</div>
          
          <template v-if="isEditing">
            <div class="edit-controls">
              <select 
                :value="string.note.slice(0, -1)" 
                @change="e => updateString(index, e.target.value, string.note.slice(-1))"
                class="note-select"
              >
                <option v-for="n in notes" :key="n" :value="n">{{ n }}</option>
              </select>
              <select 
                :value="string.note.slice(-1)" 
                @change="e => updateString(index, string.note.slice(0, -1), e.target.value)"
                class="octave-select"
              >
                <option v-for="o in octaves" :key="o" :value="o">{{ o }}</option>
              </select>
            </div>
            <div class="string-freq small">{{ string.freq }}</div>
          </template>
          
          <template v-else>
            <div class="string-note">{{ string.note }}</div>
            <div class="string-freq">{{ string.freq }} Hz</div>
          </template>
        </div>
      </div>

      <!-- 当前检测 -->
      <div class="detected-pitch" :class="{ accurate: detectedNote && detectedNote !== '--' && Math.abs(cents) <= 5 }">
        <div class="pitch-note">{{ detectedNote || '--' }}</div>
        <div class="pitch-freq">{{ detectedFrequency || '--' }}</div>
        <div class="accurate-badge">
          ✓ 音准准确
        </div>
      </div>

      <!-- 音准指示器 */
      <div class="tuner-indicator">
        <div class="indicator-scale">
          <div class="tick" v-for="i in 21" :key="i"></div>
        </div>
        <div 
          class="indicator-needle" 
          :style="{ transform: `translateX(${needlePosition}px)` }"
          :class="needleClass"
        ></div>
        <div class="indicator-labels">
          <span>偏低</span>
          <span class="center">准确</span>
          <span>偏高</span>
        </div>
      </div>

      <!-- 偏差显示 -->
      <div class="cents-display">
        {{ cents !== null ? (cents > 0 ? '+' : '') + cents + ' cents' : '&nbsp;' }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue';

const props = defineProps({
  isActive: Boolean,
  detectedNote: String,
  detectedPitch: Number
});

defineEmits(['close']);

// 标准吉他音弦（从低到高：E A D G B E）
const guitarStrings = ref([
  { name: '1弦', note: 'E4', freq: 329.63 },
  { name: '2弦', note: 'B3', freq: 246.94 },
  { name: '3弦', note: 'G3', freq: 196.00 },
  { name: '4弦', note: 'D3', freq: 146.83 },
  { name: '5弦', note: 'A2', freq: 110.00 },
  { name: '6弦', note: 'E2', freq: 82.41 }
]);

// 加载保存的调音配置
const savedTuning = localStorage.getItem('guitar-tuning');
if (savedTuning) {
  try {
    guitarStrings.value = JSON.parse(savedTuning);
  } catch (e) {
    console.error('Failed to load tuning:', e);
  }
}

const isEditing = ref(false);
const showPresets = ref(false);

const notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
const octaves = [2, 3, 4];

// 计算频率
const calculateFreq = (noteName) => {
  const note = noteName.slice(0, -1);
  const octave = parseInt(noteName.slice(-1));
  
  const semitonesFromA4 = 
    (octaves.indexOf(octave) - octaves.indexOf(4)) * 12 + 
    (notes.indexOf(note) - notes.indexOf('A'));
    
  // A4 = 440Hz
  // 公式: f = 440 * 2^(n/12)
  // 这里我们需要手动计算相对于A4的半音数
  // A4 is index 9 in notes, octave 4
  
  const noteIndex = notes.indexOf(note);
  const a4Index = notes.indexOf('A');
  const deltaSemitones = (octave - 4) * 12 + (noteIndex - a4Index);
  
  return 440 * Math.pow(2, deltaSemitones / 12);
};

const updateString = (index, note, octave) => {
  const newNote = note + octave;
  const newFreq = calculateFreq(newNote);
  guitarStrings.value[index].note = newNote;
  guitarStrings.value[index].freq = parseFloat(newFreq.toFixed(2));
  saveTuning();
};

const saveTuning = () => {
  localStorage.setItem('guitar-tuning', JSON.stringify(guitarStrings.value));
};

const applyPreset = (preset) => {
  guitarStrings.value = JSON.parse(JSON.stringify(preset));
  saveTuning();
  showPresets.value = false;
  isEditing.value = false;
};

const presets = [
  {
    name: '标准调弦 (Standard E)',
    strings: [
      { name: '1弦', note: 'E4', freq: 329.63 },
      { name: '2弦', note: 'B3', freq: 246.94 },
      { name: '3弦', note: 'G3', freq: 196.00 },
      { name: '4弦', note: 'D3', freq: 146.83 },
      { name: '5弦', note: 'A2', freq: 110.00 },
      { name: '6弦', note: 'E2', freq: 82.41 }
    ]
  },
  {
    name: '降D调弦 (Drop D)',
    strings: [
      { name: '1弦', note: 'E4', freq: 329.63 },
      { name: '2弦', note: 'B3', freq: 246.94 },
      { name: '3弦', note: 'G3', freq: 196.00 },
      { name: '4弦', note: 'D3', freq: 146.83 },
      { name: '5弦', note: 'A2', freq: 110.00 },
      { name: '6弦', note: 'D2', freq: 73.42 }
    ]
  },
  {
    name: '降半音 (Eb Standard)',
    strings: [
      { name: '1弦', note: 'D#4', freq: 311.13 },
      { name: '2弦', note: 'A#3', freq: 233.08 },
      { name: '3弦', note: 'F#3', freq: 185.00 },
      { name: '4弦', note: 'C#3', freq: 138.59 },
      { name: '5弦', note: 'G#2', freq: 103.83 },
      { name: '6弦', note: 'D#2', freq: 77.78 }
    ]
  },
  {
    name: '开放D调弦 (Open D)',
    strings: [
      { name: '1弦', note: 'D4', freq: 293.66 },
      { name: '2弦', note: 'A3', freq: 220.00 },
      { name: '3弦', note: 'F#3', freq: 185.00 },
      { name: '4弦', note: 'D3', freq: 146.83 },
      { name: '5弦', note: 'A2', freq: 110.00 },
      { name: '6弦', note: 'D2', freq: 73.42 }
    ]
  },
  {
    name: 'DADGAD (Celtic)',
    strings: [
      { name: '1弦', note: 'D4', freq: 293.66 },
      { name: '2弦', note: 'A3', freq: 220.00 },
      { name: '3弦', note: 'G3', freq: 196.00 },
      { name: '4弦', note: 'D3', freq: 146.83 },
      { name: '5弦', note: 'A2', freq: 110.00 },
      { name: '6弦', note: 'D2', freq: 73.42 }
    ]
  }
];

const detectedFrequency = computed(() => {
  return props.detectedPitch ? props.detectedPitch.toFixed(2) + ' Hz' : null;
});

const isNearNote = (note) => {
  if (!props.detectedNote) return false;
  // 精确匹配完整音符（包括八度）
  return props.detectedNote === note;
};

// 计算音分偏差 (cents)
const cents = computed(() => {
  if (!props.detectedPitch) return null;
  
  const freq = props.detectedPitch;
  const nearestString = guitarStrings.value.reduce((prev, curr) => {
    return Math.abs(curr.freq - freq) < Math.abs(prev.freq - freq) ? curr : prev;
  });
  
  // 音分计算: 1200 * log2(f1/f2)
  const centsValue = Math.round(1200 * Math.log2(freq / nearestString.freq));
  return centsValue;
});

// 指针位置 (-100 到 +100 像素)
const needlePosition = computed(() => {
  if (cents.value === null) return 0;
  // 限制在 -50 到 +50 cents 范围内
  const clampedCents = Math.max(-50, Math.min(50, cents.value));
  return (clampedCents / 50) * 100; // 转换为像素
});

const needleClass = computed(() => {
  if (cents.value === null) return '';
  if (Math.abs(cents.value) <= 5) return 'accurate';
  if (Math.abs(cents.value) <= 15) return 'close';
  return 'off';
});
</script>

<style scoped>
.tuner-panel {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: linear-gradient(135deg, #1e1e2e 0%, #2a2a4a 100%);
  border: 2px solid #42b883;
  border-radius: 12px;
  padding: 20px;
  z-index: 1000;
  min-width: 400px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);
}

.tuner-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 10px;
  border-bottom: 1px solid #3a3a5a;
}

.tuner-header h3 {
  margin: 0;
  color: #42b883;
  font-size: 1.2rem;
}

.close-btn {
  background: transparent;
  border: none;
  color: #888;
  font-size: 1.5rem;
  cursor: pointer;
  padding: 0;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  color: #e74c3c;
  background: rgba(231, 76, 60, 0.1);
  border-radius: 4px;
}

.strings {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 8px;
  margin-bottom: 20px;
}

/* 响应式网格布局 */
@media (max-width: 600px) {
  .strings {
    grid-template-columns: repeat(3, 1fr);
  }
  
  /* 移动端调低弦的字体大小以适应 */
  .string-note {
    font-size: 0.9rem;
  }
}

.string-item {
  text-align: center;
  padding: 8px;
  background: #2a2a4a;
  border-radius: 6px;
  border: 2px solid transparent;
  transition: all 0.2s;
}

.string-item.active {
  border-color: #42b883;
  background: rgba(66, 184, 131, 0.1);
}

.string-name {
  font-size: 0.7rem;
  color: #888;
  margin-bottom: 2px;
}

.string-note {
  font-size: 1rem;
  font-weight: bold;
  color: #e0e0e0;
  margin-bottom: 2px;
}

.string-freq {
  font-size: 0.7rem;
  color: #666;
}

.detected-pitch {
  text-align: center;
  margin-bottom: 20px;
  padding: 15px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
  border: 3px solid transparent; /* 预留边框空间防止抖动 */
  transition: all 0.3s ease;
  min-height: 150px; /* 预留高度给徽章 */
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}

.detected-pitch.accurate {
  background: rgba(66, 184, 131, 0.2);
  border: 3px solid #42b883;
  box-shadow: 0 0 20px rgba(66, 184, 131, 0.5);
  animation: accurate-pulse 1.5s ease-in-out infinite;
}

@keyframes accurate-pulse {
  0%, 100% {
    box-shadow: 0 0 20px rgba(66, 184, 131, 0.5);
  }
  50% {
    box-shadow: 0 0 30px rgba(66, 184, 131, 0.8);
  }
}

.pitch-note {
  font-size: 3rem;
  font-weight: bold;
  color: #e0e0e0;
  font-family: monospace;
  transition: all 0.3s ease;
}

.detected-pitch.accurate .pitch-note {
  color: #42b883;
  text-shadow: 0 0 10px rgba(66, 184, 131, 0.8);
  transform: scale(1.1);
}

.pitch-freq {
  font-size: 1rem;
  color: #888;
  margin-top: 5px;
}

.accurate-badge {
  margin-top: 10px;
  padding: 8px 16px;
  background: #42b883;
  color: white;
  border-radius: 20px;
  font-weight: bold;
  font-size: 1rem;
  display: inline-block;
  opacity: 0;           /* 默认隐藏但占位 */
  transform: scale(0.8);
  transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.detected-pitch.accurate .accurate-badge {
  opacity: 1;
  transform: scale(1);
  animation: none; /* 移除原来的bounce动画，改用transition */
}

.tuner-indicator {
  position: relative;
  margin: 30px 0;
  padding: 0 20px;
}

.indicator-scale {
  display: flex;
  justify-content: space-between;
  height: 20px;
  position: relative;
  background: linear-gradient(to right, #e74c3c, #f39c12, #42b883, #f39c12, #e74c3c);
  border-radius: 10px;
  overflow: hidden;
}

.tick {
  width: 2px;
  height: 100%;
  background: rgba(255, 255, 255, 0.3);
}

.indicator-needle {
  position: absolute;
  top: -10px;
  left: 50%;
  width: 4px;
  height: 40px;
  background: white;
  border-radius: 2px;
  transition: transform 0.1s ease-out;
  box-shadow: 0 0 10px rgba(255, 255, 255, 0.5);
}

.indicator-needle::after {
  content: '';
  position: absolute;
  top: -8px;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-top: 10px solid white;
}

.indicator-needle.accurate {
  background: #42b883;
}

.indicator-needle.close {
  background: #f39c12;
}

.indicator-needle.off {
  background: #e74c3c;
}

.indicator-labels {
  display: flex;
  justify-content: space-between;
  margin-top: 10px;
  font-size: 0.8rem;
  color: #888;
}

.indicator-labels .center {
  color: #42b883;
  font-weight: bold;
}

.cents-display {
  text-align: center;
  font-size: 1.5rem;
  font-weight: bold;
  color: #42b883;
  font-family: monospace;
  min-height: 1.8rem; /* 预留高度防止跳动 */
  margin-top: 10px;
}
</style>

<style scoped>
/* ... existing styles ... */

.header-controls {
  display: flex;
  gap: 10px;
  align-items: center;
}

.text-btn {
  background: transparent;
  border: 1px solid #42b883;
  color: #42b883;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s;
}

.text-btn:hover, .text-btn.active {
  background: #42b883;
  color: white;
}

.edit-controls {
  display: flex;
  gap: 4px;
  justify-content: center;
  align-items: center;
  margin-bottom: 2px;
}

.note-select, .octave-select {
  background: #1e1e2e;
  border: 1px solid #444;
  color: white;
  border-radius: 4px;
  padding: 2px;
  font-size: 0.9rem;
  width: 45px;
}

.string-item.editing {
  border-color: #f39c12;
  background: rgba(243, 156, 18, 0.1);
}

.string-freq.small {
  font-size: 0.6rem;
  color: #666;
}

.presets-panel {
  position: absolute;
  top: 60px;
  right: 20px;
  background: #2a2a4a;
  border: 1px solid #444;
  border-radius: 8px;
  padding: 10px;
  z-index: 1010;
  box-shadow: 0 5px 15px rgba(0,0,0,0.5);
  max-height: 300px;
  overflow-y: auto;
}

.preset-item {
  padding: 8px 12px;
  cursor: pointer;
  border-radius: 4px;
  color: #e0e0e0;
  font-size: 0.9rem;
  transition: background 0.2s;
}

.preset-item:hover {
  background: rgba(66, 184, 131, 0.2);
  color: #42b883;
}
</style>
