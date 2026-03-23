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

<style src="./PixelInfoPanel.css" scoped></style>
