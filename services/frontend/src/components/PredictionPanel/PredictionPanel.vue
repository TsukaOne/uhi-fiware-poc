<template>
  <Transition name="panel-slide">
    <div v-if="visible" class="prediction-panel">

      <!-- Header -->
      <div class="panel-header">
        <div class="panel-header-left">
          <div class="panel-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="#22d3a0" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </div>
          <div>
            <div class="panel-title">UHI Prediction</div>
            <div class="panel-subtitle">{{ predictionResult ? 'Comparison view' : 'Run simulation' }}</div>
          </div>
        </div>
        <button class="panel-close" @click="$emit('close')">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M1 1l12 12M13 1L1 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </button>
      </div>

      <!-- Zone summary -->
      <div class="zone-summary" v-if="geometry">
        <div class="zone-summary-label">
          <i :class="geometry.type === 'polygon' ? 'fas fa-draw-polygon' : 'fas fa-vector-square'"></i>
          {{ geometry.type === 'polygon' ? 'Polygon' : 'Bounding Box' }}
        </div>
        <div class="zone-summary-info" v-if="geometry.type === 'boundingBox' && geometry.bounds">
          <span>N {{ geometry.bounds.maxLat.toFixed(4) }}°</span>
          <span>S {{ geometry.bounds.minLat.toFixed(4) }}°</span>
          <span>E {{ geometry.bounds.maxLon.toFixed(4) }}°</span>
          <span>W {{ geometry.bounds.minLon.toFixed(4) }}°</span>
        </div>
        <div class="zone-summary-info" v-else-if="geometry.summary">
          {{ geometry.summary.pointCount }} points
        </div>
      </div>

      <!-- Zone Points Toggle (collapsed by default) -->
      <button class="pp-dropdown-toggle" @click="showPoints = !showPoints">
        <i :class="showPoints ? 'fas fa-chevron-up' : 'fas fa-chevron-down'"></i>
        <span>Zone Points ({{ pointCount }})</span>
      </button>
      <div v-if="showPoints" class="pp-dropdown-body">
        <div class="pp-points-list" v-if="geometry?.geoJSON?.coordinates">
          <div v-for="(coord, i) in geometry.geoJSON.coordinates[0].slice(0, -1)" :key="i" class="pp-point-row">
            <span class="pp-point-idx">{{ i + 1 }}</span>
            <span class="pp-point-val">{{ coord[1].toFixed(5) }}, {{ coord[0].toFixed(5) }}</span>
          </div>
        </div>
        <div class="pp-points-list" v-else-if="geometry?.bounds">
          <div class="pp-point-row">
            <span class="pp-point-idx">NW</span>
            <span class="pp-point-val">{{ geometry.bounds.maxLat.toFixed(5) }}, {{ geometry.bounds.minLon.toFixed(5) }}</span>
          </div>
          <div class="pp-point-row">
            <span class="pp-point-idx">SE</span>
            <span class="pp-point-val">{{ geometry.bounds.minLat.toFixed(5) }}, {{ geometry.bounds.maxLon.toFixed(5) }}</span>
          </div>
        </div>
      </div>

      <!-- Objects dropdown (collapsed by default) -->
      <button v-if="zoneObjects.length > 0" class="pp-dropdown-toggle" @click="showObjects = !showObjects">
        <i :class="showObjects ? 'fas fa-chevron-up' : 'fas fa-chevron-down'"></i>
        <span>Objects ({{ zoneObjects.length }})</span>
      </button>
      <div v-if="showObjects && zoneObjects.length > 0" class="pp-dropdown-body">
        <div class="pp-objects-list">
          <div v-for="obj in zoneObjects" :key="obj.id" class="pp-object-row">
            <span class="pp-object-name">{{ obj.label || obj.type }}</span>
            <span class="pp-object-pos">{{ obj.lat.toFixed(4) }}, {{ obj.lon.toFixed(4) }}</span>
          </div>
        </div>
      </div>

      <!-- Objects summary badge (when not expanded) -->
      <div class="objects-summary" v-if="zoneObjects.length > 0 && !showObjects">
        <i class="fas fa-cubes"></i>
        {{ zoneObjects.length }} object{{ zoneObjects.length > 1 ? 's' : '' }} placed
      </div>

      <!-- Pre-prediction: UHI baseline stats from zone analysis -->
      <div v-if="!predictionResult && zoneStats?.layer_stats?.['uhi']" class="zone-uhi-baseline">
        <div class="panel-divider">
          <span>Current UHI values</span>
        </div>
        <div class="result-cards">
          <div class="result-card main">
            <span class="rc-label">Mean UHI</span>
            <span class="rc-value heat">{{ zoneStats.layer_stats['uhi'].mean?.toFixed(2) }}°C</span>
          </div>
          <div class="result-card">
            <span class="rc-label">Min</span>
            <span class="rc-value">{{ zoneStats.layer_stats['uhi'].min?.toFixed(2) }}°C</span>
          </div>
          <div class="result-card">
            <span class="rc-label">Max</span>
            <span class="rc-value">{{ zoneStats.layer_stats['uhi'].max?.toFixed(2) }}°C</span>
          </div>
        </div>
      </div>

      <!-- Pre-prediction: button + zone size warning -->
      <div v-if="!predictionResult" class="predict-section">
        <div v-if="estimatedPixels > 50000" class="zone-size-warning">
          <i class="fas fa-clock"></i>
          <span>
            Large zone (~{{ Math.round(estimatedPixels / 1000) }}k pixels) — prediction may take
            {{ estimatedPixels > 200000 ? 'several minutes' : 'up to a minute' }}.
          </span>
        </div>
        <button class="btn-predict" @click="launchPrediction" :class="{ loading: isLoading }">
          <span v-if="!isLoading">
            <i class="fas fa-bolt"></i>
            Run Prediction
          </span>
          <span v-else class="loading-state">
            <span class="loading-dots"><span>·</span><span>·</span><span>·</span></span>
            <span class="loading-timer" v-if="elapsedSeconds > 0">{{ elapsedSeconds }}s</span>
          </span>
        </button>
      </div>

      <!-- Post-prediction: comparison UI -->
      <Transition name="result-fade">
        <div v-if="predictionResult" class="comparison-section">

          <!-- UHI Results -->
          <div class="panel-divider">
            <span>Prediction Results</span>
          </div>

          <div class="result-cards">
            <div class="result-card main">
              <span class="rc-label">Mean UHI</span>
              <span class="rc-value heat">{{ predictionResult.stats.mean_uhi.toFixed(2) }}°C</span>
            </div>
            <div class="result-card">
              <span class="rc-label">Min</span>
              <span class="rc-value">{{ predictionResult.stats.min_uhi.toFixed(2) }}°C</span>
            </div>
            <div class="result-card">
              <span class="rc-label">Max</span>
              <span class="rc-value">{{ predictionResult.stats.max_uhi.toFixed(2) }}°C</span>
            </div>
          </div>

          <div class="result-meta">
            <span><i class="fas fa-th"></i> {{ predictionResult.stats.pixel_count.toLocaleString() }} px</span>
            <span v-if="predictionResult.stats.duration_ms">
              <i class="fas fa-clock"></i> {{ (predictionResult.stats.duration_ms / 1000).toFixed(1) }}s
            </span>
          </div>

          <!-- UHI Before / After comparison -->
          <div v-if="zoneStats?.layer_stats?.['uhi']" class="uhi-comparison-section">
            <div class="panel-divider">
              <span>UHI Before / After</span>
            </div>
            <div class="uhi-comparison-grid">
              <div class="uhi-cmp-row">
                <span class="uhi-cmp-metric">Mean</span>
                <span class="uhi-cmp-before">{{ zoneStats.layer_stats['uhi'].mean?.toFixed(2) }}°C</span>
                <i class="fas fa-arrow-right uhi-cmp-arrow"></i>
                <span class="uhi-cmp-after">{{ predictionResult.stats.mean_uhi.toFixed(2) }}°C</span>
                <span class="uhi-cmp-delta" :class="getUhiDeltaClass('mean')">{{ getUhiDeltaFormatted('mean') }}</span>
              </div>
              <div class="uhi-cmp-row">
                <span class="uhi-cmp-metric">Min</span>
                <span class="uhi-cmp-before">{{ zoneStats.layer_stats['uhi'].min?.toFixed(2) }}°C</span>
                <i class="fas fa-arrow-right uhi-cmp-arrow"></i>
                <span class="uhi-cmp-after">{{ predictionResult.stats.min_uhi.toFixed(2) }}°C</span>
                <span class="uhi-cmp-delta" :class="getUhiDeltaClass('min')">{{ getUhiDeltaFormatted('min') }}</span>
              </div>
              <div class="uhi-cmp-row">
                <span class="uhi-cmp-metric">Max</span>
                <span class="uhi-cmp-before">{{ zoneStats.layer_stats['uhi'].max?.toFixed(2) }}°C</span>
                <i class="fas fa-arrow-right uhi-cmp-arrow"></i>
                <span class="uhi-cmp-after">{{ predictionResult.stats.max_uhi.toFixed(2) }}°C</span>
                <span class="uhi-cmp-delta" :class="getUhiDeltaClass('max')">{{ getUhiDeltaFormatted('max') }}</span>
              </div>
            </div>
          </div>

          <!-- Before / After comparison (input layers) -->
          <div class="panel-divider" v-if="zoneStats && hasComparison">
            <span>Input Layer Comparison</span>
          </div>

          <div v-if="zoneStats && hasComparison" class="comparison-list">
            <div
              v-for="layer in comparisonLayers"
              :key="layer.key"
              class="comparison-row"
            >
              <div class="cmp-header">
                <i :class="layer.icon" :style="{ color: layer.color }"></i>
                <span class="cmp-name">{{ layer.label }}</span>
              </div>
              <div class="cmp-values" v-if="zoneStats.layer_stats[layer.key] && afterStats?.layer_stats[layer.key]">
                <div class="cmp-col">
                  <span class="cmp-label">Before</span>
                  <span class="cmp-val">{{ formatVal(zoneStats.layer_stats[layer.key].mean, layer.unit) }}</span>
                </div>
                <div class="cmp-arrow">
                  <i class="fas fa-arrow-right"></i>
                </div>
                <div class="cmp-col">
                  <span class="cmp-label">After</span>
                  <span class="cmp-val">{{ formatVal(afterStats.layer_stats[layer.key].mean, layer.unit) }}</span>
                </div>
                <div class="cmp-col delta" v-if="getDelta(layer.key) !== null">
                  <span class="cmp-label">Delta</span>
                  <span class="cmp-val" :class="getDeltaClass(layer.key)">
                    {{ getDeltaFormatted(layer.key, layer.unit) }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- Actions after prediction -->
          <div class="post-actions">
            <button class="btn-rerun" @click="rerunPrediction">
              <i class="fas fa-redo"></i>
              Re-run
            </button>
          </div>

        </div>
      </Transition>

      <!-- Error -->
      <Transition name="result-fade">
        <div v-if="predictionError" class="error-result">
          <div class="error-header">
            <i class="fas fa-exclamation-triangle"></i>
            Prediction Failed
          </div>
          <p class="error-msg">{{ predictionError }}</p>
          <button class="btn-rerun" @click="launchPrediction">
            <i class="fas fa-redo"></i> Retry
          </button>
        </div>
      </Transition>

    </div>
  </Transition>
</template>

<script setup>
import { ref, computed, onBeforeUnmount } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  geometry: { type: Object, default: null },
  zoneObjects: { type: Array, default: () => [] },
  zoneStats: { type: Object, default: null },
})

const emit = defineEmits(['close', 'predict'])

import { predictionApi } from '../../services/predictionApi.js'

const isLoading = ref(false)
const elapsedSeconds = ref(0)
let elapsedTimer = null

// Collapsible sections (both hidden at t0)
const showPoints = ref(false)
const showObjects = ref(false)

const pointCount = computed(() => {
  if (props.geometry?.geoJSON?.coordinates) {
    return props.geometry.geoJSON.coordinates[0].length - 1
  }
  if (props.geometry?.bounds) return 4
  return 0
})

// Average metres per degree of latitude (equatorial approximation, accurate to ~1% for Brussels)
const METERS_PER_DEGREE = 111_000
// Layer resolution: each pixel covers ~10 m × 10 m
const LAYER_RESOLUTION_M = 10
// Polygon bounding-box over-counts area; 0.6 corrects for the average ratio of
// inscribed polygon area vs. its axis-aligned bounding box
const POLYGON_BBOX_FILL_RATIO = 0.6

// Rough pixel estimate based on zone area at LAYER_RESOLUTION_M resolution
const estimatedPixels = computed(() => {
  if (!props.geometry) return 0
  const bounds = props.geometry.bounds
  if (bounds) {
    const latDiff = Math.abs(bounds.maxLat - bounds.minLat)
    const lonDiff = Math.abs(bounds.maxLon - bounds.minLon)
    const latPixels = (latDiff * METERS_PER_DEGREE) / LAYER_RESOLUTION_M
    const lonPixels = (lonDiff * METERS_PER_DEGREE * Math.cos(bounds.minLat * Math.PI / 180)) / LAYER_RESOLUTION_M
    return Math.round(latPixels * lonPixels)
  }
  const pts = props.geometry.points
  if (pts && pts.length >= 3) {
    const lats = pts.map(p => p.latitude)
    const lons = pts.map(p => p.longitude)
    const latDiff = Math.max(...lats) - Math.min(...lats)
    const lonDiff = Math.max(...lons) - Math.min(...lons)
    const latPixels = (latDiff * METERS_PER_DEGREE) / LAYER_RESOLUTION_M
    const lonPixels = (lonDiff * METERS_PER_DEGREE * Math.cos(Math.min(...lats) * Math.PI / 180)) / LAYER_RESOLUTION_M
    return Math.round(latPixels * lonPixels * POLYGON_BBOX_FILL_RATIO)
  }
  return 0
})

function startTimer() {
  elapsedSeconds.value = 0
  elapsedTimer = setInterval(() => { elapsedSeconds.value++ }, 1000)
}

function stopTimer() {
  if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null }
}

onBeforeUnmount(() => stopTimer())
const predictionResult = ref(null)
const predictionError = ref(null)
const afterStats = ref(null)

const comparisonLayers = [
  { key: 'ndvi',              label: 'NDVI',             icon: 'fas fa-leaf',             color: '#4ade80', unit: '' },
  { key: 'ndwi',              label: 'NDWI',             icon: 'fas fa-droplet',          color: '#38bdf8', unit: '' },
  { key: 'ndbi',              label: 'NDBI',             icon: 'fas fa-city',             color: '#94a3b8', unit: '' },
  { key: 'imperviousness',    label: 'Imperviousness',   icon: 'fas fa-road',             color: '#6b7280', unit: '' },
  { key: 'albedo',            label: 'Albedo',           icon: 'fas fa-sun',              color: '#fbbf24', unit: '' },
  { key: 'dsm',               label: 'DSM',              icon: 'fas fa-mountain-sun',     color: '#c084fc', unit: 'm' },
  { key: 'building_height',   label: 'Building Height',  icon: 'fas fa-building',         color: '#f59e0b', unit: 'm' },
]

const hasComparison = computed(() => {
  return props.zoneObjects.length > 0 && afterStats.value
})

function formatVal(val, unit) {
  if (val === null || val === undefined) return '—'
  const f = Math.abs(val) >= 100 ? val.toFixed(1) : val.toFixed(3)
  return unit ? `${f} ${unit}` : f
}

function getDelta(key) {
  const before = props.zoneStats?.layer_stats?.[key]?.mean
  const after = afterStats.value?.layer_stats?.[key]?.mean
  if (before == null || after == null) return null
  return after - before
}

function getDeltaFormatted(key, unit) {
  const d = getDelta(key)
  if (d === null) return '—'
  const sign = d >= 0 ? '+' : ''
  const f = Math.abs(d) >= 100 ? d.toFixed(1) : d.toFixed(3)
  return unit ? `${sign}${f} ${unit}` : `${sign}${f}`
}

function getDeltaClass(key) {
  const d = getDelta(key)
  if (d === null) return ''
  // For vegetation-related: positive is good, for imperviousness: positive is bad
  const greenPositive = ['ndvi', 'ndwi', 'albedo']
  if (greenPositive.includes(key)) {
    return d > 0 ? 'positive' : d < 0 ? 'negative' : ''
  }
  return d > 0 ? 'negative' : d < 0 ? 'positive' : ''
}

// UHI comparison helpers (original zone vs simulated)
const uhiMetricMap = {
  mean: { before: 'mean', after: 'mean_uhi' },
  min:  { before: 'min',  after: 'min_uhi' },
  max:  { before: 'max',  after: 'max_uhi' },
}

function getUhiDelta(metric) {
  const map = uhiMetricMap[metric]
  if (!map) return null
  const before = props.zoneStats?.layer_stats?.['uhi']?.[map.before]
  const after = predictionResult.value?.stats?.[map.after]
  if (before == null || after == null) return null
  return after - before
}

function getUhiDeltaFormatted(metric) {
  const d = getUhiDelta(metric)
  if (d === null) return '—'
  const sign = d >= 0 ? '+' : ''
  return `${sign}${d.toFixed(2)}°C`
}

function getUhiDeltaClass(metric) {
  const d = getUhiDelta(metric)
  if (d === null) return ''
  // For UHI: lower is better (positive = worse, negative = better)
  return d > 0 ? 'negative' : d < 0 ? 'positive' : ''
}

async function launchPrediction() {
  if (!props.geometry?.geoJSON) return

  isLoading.value = true
  predictionResult.value = null
  predictionError.value = null
  afterStats.value = null
  startTimer()

  try {
    const body = {
      geometry: props.geometry.geoJSON,
      objects: (props.zoneObjects || []).map(o => ({
        type: o.type,
        lon: o.lon,
        lat: o.lat,
      })),
    }

    const data = await predictionApi.predictZone(body)
    predictionResult.value = data
    if (data.stats?.layer_stats) {
      afterStats.value = { layer_stats: data.stats.layer_stats }
    }

    emit('predict', {
      geometry: props.geometry,
      result: data,
    })

  } catch (err) {
    console.error('Zone prediction failed:', err)
    predictionError.value = err.message || 'Unknown error'
  } finally {
    isLoading.value = false
    stopTimer()
  }
}

function rerunPrediction() {
  predictionResult.value = null
  predictionError.value = null
  afterStats.value = null
  launchPrediction()
}
</script>

<style src="./PredictionPanel.css" scoped></style>