<template>
  <div class="tuner-panel" v-if="isActive">
    <div class="tuner-header">
      <h3>🎸 吉他调音器</h3>
      <button @click="$emit('close')" class="close-btn">✕</button>
    </div>

    <div class="tuner-content">
      <!-- 标准音弦选择 -->
      <div class="strings">
        <div 
          v-for="string in guitarStrings" 
          :key="string.name"
          class="string-item"
          :class="{ active: isNearNote(string.note) }"
        >
          <div class="string-name">{{ string.name }}</div>
          <div class="string-note">{{ string.note }}</div>
          <div class="string-freq">{{ string.freq }} Hz</div>
        </div>
      </div>

      <!-- 当前检测 -->
      <div class="detected-pitch" :class="{ accurate: detectedNote && detectedNote !== '--' && Math.abs(cents) <= 5 }">
        <div class="pitch-note">{{ detectedNote || '--' }}</div>
        <div class="pitch-freq">{{ detectedFrequency || '--' }}</div>
        <div v-if="detectedNote && detectedNote !== '--' && Math.abs(cents) <= 5" class="accurate-badge">
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
      <div class="cents-display" v-if="cents !== null">
        {{ cents > 0 ? '+' : '' }}{{ cents }} cents
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
const guitarStrings = [
  { name: '1弦', note: 'E4', freq: 329.63 },
  { name: '2弦', note: 'B3', freq: 246.94 },
  { name: '3弦', note: 'G3', freq: 196.00 },
  { name: '4弦', note: 'D3', freq: 146.83 },
  { name: '5弦', note: 'A2', freq: 110.00 },
  { name: '6弦', note: 'E2', freq: 82.41 }
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
  const nearestString = guitarStrings.reduce((prev, curr) => {
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
  transition: all 0.3s ease;
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
  animation: badge-bounce 0.5s ease-out;
}

@keyframes badge-bounce {
  0% {
    transform: scale(0);
  }
  50% {
    transform: scale(1.1);
  }
  100% {
    transform: scale(1);
  }
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
}
</style>
