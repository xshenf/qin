<template>
  <div class="performance-bar">
    <div class="pitch-stream">
      <transition-group name="list" tag="div" class="stream-container">
        <!-- History Stream -->
        <div 
          v-for="item in pitchHistory" 
          :key="item.id" 
          class="pitch-item"
          :class="getPitchClass(item)"
        >
          <span class="note-name">{{ item.note }}</span>
          <span class="cents" v-if="Math.abs(item.cents) > 5">
            {{ item.cents > 0 ? '+' : '' }}{{ item.cents }}
          </span>
        </div>
      </transition-group>
    </div>

    <!-- Active Notes Display (Polyphonic) -->
    <div class="active-notes" v-if="activeNotes.length > 0">
        <div v-for="(note, index) in activeNotes" :key="index" class="current-note-card">
            <div class="main-note">{{ note.note }}</div>
             <div class="meter-container">
                <div class="meter-indicator" :style="{ left: (50 + note.cents/2) + '%' }"></div>
                <div class="meter-center"></div>
             </div>
             <div class="cents-val">{{ note.cents }}</div>
        </div>
    </div>
    <div class="active-notes-placeholder" v-else>
        Listening...
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';

const props = defineProps({
  detectedPitch: {
    type: [Object, Array], // Accepts Array now
    default: () => []
  }
});

const pitchHistory = ref([]);
const activeNotes = ref([]);
let idCounter = 0;

// Update history when new pitch arrives
watch(() => props.detectedPitch, (newVal) => {
  // Handle Array input
  let notes = [];
  if (Array.isArray(newVal)) {
      notes = newVal;
  } else if (newVal) {
      notes = [newVal];
  }

  activeNotes.value = notes;

  if (notes.length === 0) return;

  // Add to history:
  // Strategy: Add the "loudest" note to history if it's new?
  // Or add all? Adding all clutter the stream.
  // Let's add the primary candidate (index 0).

  const primary = notes[0];
  const lastItem = pitchHistory.value[pitchHistory.value.length - 1];
  const now = Date.now();
  
  // Throttle history updates (avoid spamming same note)
  if (!lastItem || lastItem.note !== primary.note || (now - lastItem.timestamp > 1000)) {
     pitchHistory.value.push({
         id: idCounter++,
         note: primary.note,
         cents: primary.cents,
         timestamp: now
     });
     
     // Keep last 10
     if (pitchHistory.value.length > 20) {
         pitchHistory.value.shift();
     }
  } else {
     // Update existing item
     lastItem.cents = primary.cents;
     lastItem.timestamp = now; 
  }
});

const getPitchClass = (item) => {
    const absCents = Math.abs(item.cents);
    if (absCents < 15) return 'perfect';
    if (absCents < 30) return 'good';
    return 'bad';
};
</script>

<style scoped>
.performance-bar {
  display: flex;
  align-items: center;
  background: rgba(0, 0, 0, 0.8);
  height: 80px; /* Increased height for cards */
  padding: 0 16px;
  color: white;
  border-top: 1px solid #333;
  overflow: hidden;
}

.pitch-stream {
  flex: 1;
  overflow: hidden;
  mask-image: linear-gradient(to right, transparent, black 10%);
  margin-right: 20px;
}

.stream-container {
  display: flex;
  flex-direction: row-reverse; 
  justify-content: flex-end;
  gap: 8px;
  opacity: 0.6; /* Dim history */
}

.pitch-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 30px;
  padding: 2px 4px;
  border-radius: 4px;
  background: #222;
  border: 1px solid #444;
  font-size: 0.8em;
}

.pitch-item.perfect { border-color: #42b883; color: #42b883; }
.pitch-item.good { border-color: #aaa; color: #eee; }
.pitch-item.bad { border-color: #ff4444; color: #ff4444; }

.active-notes {
    display: flex;
    gap: 10px;
    padding-left: 20px;
    border-left: 1px solid #444;
}

.active-notes-placeholder {
    margin-left: 20px;
    color: #555;
    font-size: 0.9em;
    font-style: italic;
    width: 100px;
    text-align: center;
}

.current-note-card {
    background: #2a2a3a;
    border: 1px solid #444;
    border-radius: 6px;
    padding: 5px 10px;
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 60px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.5);
}

.main-note {
    font-size: 1.2em;
    font-weight: bold;
    color: #fff;
}

.cents-val {
    font-size: 0.7em;
    color: #888;
    margin-top: 2px;
}

.meter-container {
    width: 40px;
    height: 4px;
    background: #111;
    position: relative;
    margin: 4px 0;
    border-radius: 2px;
}
.meter-center {
    position: absolute;
    left: 50%;
    top: 0; bottom: 0;
    width: 1px;
    background: #666;
}
.meter-indicator {
    position: absolute;
    top: -2px;
    width: 4px;
    height: 8px;
    background: #42b883;
    border-radius: 2px;
    transform: translateX(-50%);
}
/* ... animations ... */
/* Animations */
.list-enter-active,
.list-leave-active {
  transition: all 0.3s ease;
}
.list-enter-from,
.list-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>
