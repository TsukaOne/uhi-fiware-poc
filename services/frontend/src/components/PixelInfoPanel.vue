<template>
  <Transition name="pixel-fade">
    <div v-if="visible && pixelData" class="pixel-info-panel" :style="panelStyle">
      <!-- Header -->
      <div class="pip-header">
        <span class="pip-title">
          <i class="fas fa-crosshairs"></i> Pixel Values
        </span>
        <button class="pip-close" @click="$emit('close')">
          <i class="fas fa-times"></i>
        </button>
      </div>

      <!-- Coordinates -->
      <div class="pip-coords">
        <span>{{ pixelData.lon.toFixed(6) }}°, {{ pixelData.lat.toFixed(6) }}°</span>
      </div>

      <!-- Loading -->
      <div v-if="isLoading" class="pip-loading">
        <div class="loading-spinner"></div>
      </div>

      <!-- Values -->
      <div v-else class="pip-values">
        <div
          v-for="layer in displayLayers"
          :key="layer.key"
          class="pip-row"
          v-show="pixelData.values[layer.key] !== undefined"
        >
          <div class="pip-label">
            <i :class="layer.icon" :style="{ color: layer.color }"></i>
            <span>{{ layer.label }}</span>
          </div>
          <span class="pip-val" v-if="pixelData.values[layer.key] !== null">
            {{ formatValue(pixelData.values[layer.key], layer.unit) }}
          </span>
          <span class="pip-val nodata" v-else>nodata</span>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  pixelData: { type: Object, default: null },
  isLoading: { type: Boolean, default: false },
  screenX: { type: Number, default: 0 },
  screenY: { type: Number, default: 0 },
})

defineEmits(['close'])

const displayLayers = [
  { key: 'ndvi',            label: 'NDVI',             icon: 'fas fa-leaf',             color: '#4ade80', unit: '' },
  { key: 'ndwi',            label: 'NDWI',             icon: 'fas fa-droplet',          color: '#38bdf8', unit: '' },
  { key: 'ndbi',            label: 'NDBI',             icon: 'fas fa-city',             color: '#94a3b8', unit: '' },
  { key: 'lst',             label: 'LST',              icon: 'fas fa-thermometer-half', color: '#f87171', unit: '°C' },
  { key: 'dtm',             label: 'DTM',              icon: 'fas fa-mountain',         color: '#a78bfa', unit: 'm' },
  { key: 'dsm',             label: 'DSM',              icon: 'fas fa-mountain-sun',     color: '#c084fc', unit: 'm' },
  { key: 'building_height', label: 'Building Ht.',     icon: 'fas fa-building',         color: '#f59e0b', unit: 'm' },
  { key: 'imperviousness',  label: 'Imperviousness',   icon: 'fas fa-road',             color: '#6b7280', unit: '' },
  { key: 'albedo',          label: 'Albedo',           icon: 'fas fa-sun',              color: '#fbbf24', unit: '' },
]

function formatValue(val, unit) {
  if (val === null || val === undefined) return '—'
  const f = Math.abs(val) >= 100 ? val.toFixed(1) : val.toFixed(4)
  return unit ? `${f} ${unit}` : f
}

const panelStyle = computed(() => {
  // Position panel near click, but keep within viewport
  const x = Math.min(props.screenX + 16, window.innerWidth - 260)
  const y = Math.min(props.screenY - 20, window.innerHeight - 400)
  return {
    left: Math.max(8, x) + 'px',
    top: Math.max(70, y) + 'px',
  }
})
</script>

<style scoped>
.pixel-info-panel {
  position: fixed;
  width: 240px;
  background: rgba(10, 14, 22, 0.97);
  backdrop-filter: blur(16px);
  border-radius: 10px;
  border: 1px solid rgba(34, 211, 160, 0.25);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.6);
  z-index: 2000;
  font-family: 'Courier New', monospace;
  overflow: hidden;
}

.pixel-fade-enter-active { transition: all 0.2s ease; }
.pixel-fade-leave-active { transition: all 0.15s ease; }
.pixel-fade-enter-from, .pixel-fade-leave-to {
  opacity: 0;
  transform: scale(0.95);
}

.pip-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  background: rgba(34, 211, 160, 0.08);
  border-bottom: 1px solid rgba(34, 211, 160, 0.12);
}

.pip-title {
  color: #22d3a0;
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}

.pip-close {
  background: none;
  border: none;
  color: rgba(255,255,255,0.4);
  cursor: pointer;
  font-size: 12px;
  padding: 2px;
  transition: color 0.15s;
}
.pip-close:hover { color: white; }

.pip-coords {
  padding: 6px 10px;
  font-size: 9px;
  color: rgba(255,255,255,0.35);
  border-bottom: 1px solid rgba(255,255,255,0.06);
  font-family: 'Courier New', monospace;
}

.pip-loading {
  display: flex;
  justify-content: center;
  padding: 16px;
}

.loading-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(34, 211, 160, 0.2);
  border-top-color: #22d3a0;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.pip-values {
  padding: 6px 0;
  max-height: 320px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(34,211,160,0.3) transparent;
}

.pip-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 10px;
  transition: background 0.1s;
}

.pip-row:hover {
  background: rgba(255,255,255,0.03);
}

.pip-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  color: rgba(255,255,255,0.55);
}

.pip-label i {
  width: 12px;
  text-align: center;
  font-size: 9px;
}

.pip-val {
  font-size: 11px;
  font-weight: 700;
  color: white;
  font-family: 'Courier New', monospace;
}

.pip-val.nodata {
  color: rgba(255,255,255,0.2);
  font-weight: 400;
  font-style: italic;
}
</style>
