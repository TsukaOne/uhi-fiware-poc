<template>
  <div class="tbase-panel">
    <div class="tbase-header">
      <i class="fas fa-thermometer-half"></i>
      <span class="tbase-title">Live Temperature</span>
      <button
        class="tbase-sync-btn"
        @click="fetchTBase"
        title="Refresh from VLINDER"
      >
        <i class="fas fa-sync-alt"></i>
      </button>
    </div>

    <div class="tbase-body">
      <div class="tbase-value-row">
        <span class="tbase-value">{{ tBase.toFixed(1) }} °C</span>
        <span class="tbase-source" :class="{ fallback: isFallback }">
          <i :class="sourceIcon"></i>
          {{ sourceLabel }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

const PREDICTION_URL = '/prediction'

const props = defineProps({
  modelValue: { type: Number, default: 15.0 },
})

const emit = defineEmits(['update:modelValue'])

const tBase = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const isFallback = ref(false)
const stationName = ref('')
let pollTimer = null

const sourceIcon = computed(() => 'fas fa-satellite-dish')

const sourceLabel = computed(() => {
  if (isFallback.value) return `${stationName.value || 'VLINDER'} (cached)`
  return stationName.value || 'VLINDER'
})

async function fetchTBase() {
  try {
    const resp = await fetch(`${PREDICTION_URL}/vlinder/t_base`)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    stationName.value = data.station_name || data.station_id
    isFallback.value = data.fallback
    tBase.value = data.value
  } catch (err) {
    console.warn('VLINDER fetch failed:', err)
    isFallback.value = true
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(fetchTBase, 10 * 60 * 1000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(() => {
  fetchTBase()
  startPolling()
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<style scoped>
.tbase-panel {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(20, 25, 35, 0.92);
  backdrop-filter: blur(8px);
  border-radius: 12px;
  padding: 10px 16px;
  z-index: 1500;
  min-width: 320px;
  color: white;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
}

.tbase-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.85);
}

.tbase-title {
  flex: 1;
}

.tbase-sync-btn {
  background: rgba(22, 163, 74, 0.3);
  border: 1px solid rgba(22, 163, 74, 0.5);
  color: #4ade80;
  border-radius: 6px;
  padding: 4px 8px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}

.tbase-sync-btn:hover {
  background: rgba(22, 163, 74, 0.5);
}

.tbase-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tbase-value-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.tbase-value {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.5px;
}

.tbase-source {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  display: flex;
  align-items: center;
  gap: 4px;
}

.tbase-source.fallback {
  color: #fbbf24;
}

.tbase-slider-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.slider-bound {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.4);
  min-width: 28px;
  text-align: center;
}

.tbase-slider {
  flex: 1;
  -webkit-appearance: none;
  appearance: none;
  height: 4px;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 2px;
  outline: none;
}

.tbase-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #16a34a;
  cursor: pointer;
  border: 2px solid white;
  box-shadow: 0 0 6px rgba(22, 163, 74, 0.5);
}

.tbase-slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #16a34a;
  cursor: pointer;
  border: 2px solid white;
  box-shadow: 0 0 6px rgba(22, 163, 74, 0.5);
}
</style>
