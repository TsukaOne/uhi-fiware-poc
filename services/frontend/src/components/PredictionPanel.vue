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

      <!-- Objects summary -->
      <div class="objects-summary" v-if="zoneObjects.length > 0">
        <i class="fas fa-cubes"></i>
        {{ zoneObjects.length }} object{{ zoneObjects.length > 1 ? 's' : '' }} placed
      </div>

      <!-- Pre-prediction: just the button -->
      <div v-if="!predictionResult" class="predict-section">
        <button class="btn-predict" @click="launchPrediction" :class="{ loading: isLoading }">
          <span v-if="!isLoading">
            <i class="fas fa-bolt"></i>
            Run Prediction
          </span>
          <span v-else class="loading-dots">
            <span>·</span><span>·</span><span>·</span>
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

          <!-- Before / After comparison -->
          <div class="panel-divider" v-if="zoneStats && hasComparison">
            <span>Before / After Comparison</span>
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
import { ref, computed } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  geometry: { type: Object, default: null },
  zoneObjects: { type: Array, default: () => [] },
  zoneStats: { type: Object, default: null },
})

const emit = defineEmits(['close', 'predict'])

const PREDICTION_URL = '/prediction'

const isLoading = ref(false)
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

async function fetchAfterStats() {
  if (!props.geometry?.geoJSON || props.zoneObjects.length === 0) {
    afterStats.value = null
    return
  }
  // We don't have a "with objects" stats route, so we skip after-stats
  // if no objects were placed. The comparison only makes sense with objects.
  // For now, we re-use the zone stats route (which doesn't apply object impacts).
  // The delta will be visible in the prediction result itself.
  afterStats.value = null
}

async function launchPrediction() {
  if (!props.geometry?.geoJSON) return

  isLoading.value = true
  predictionResult.value = null
  predictionError.value = null
  afterStats.value = null

  try {
    const body = {
      geometry: props.geometry.geoJSON,
      objects: (props.zoneObjects || []).map(o => ({
        type: o.type,
        lon: o.lon,
        lat: o.lat,
      })),
    }

    const resp = await fetch(`${PREDICTION_URL}/predict/zone`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })

    if (!resp.ok) {
      const text = await resp.text()
      throw new Error(`${resp.status}: ${text}`)
    }

    const data = await resp.json()
    predictionResult.value = data

    emit('predict', {
      geometry: props.geometry,
      result: data,
    })

  } catch (err) {
    console.error('Zone prediction failed:', err)
    predictionError.value = err.message || 'Unknown error'
  } finally {
    isLoading.value = false
  }
}

function rerunPrediction() {
  predictionResult.value = null
  predictionError.value = null
  afterStats.value = null
  launchPrediction()
}
</script>

<style scoped>
.prediction-panel {
  position: absolute;
  top: 70px;
  right: 16px;
  width: 340px;
  max-height: calc(100vh - 90px);
  overflow-y: auto;
  background: rgba(10, 14, 22, 0.97);
  backdrop-filter: blur(16px);
  border-radius: 14px;
  border: 1px solid rgba(34, 211, 160, 0.2);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255,255,255,0.04);
  z-index: 1500;
  font-family: 'Courier New', monospace;
  scrollbar-width: thin;
  scrollbar-color: rgba(34,211,160,0.3) transparent;
}

.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s ease;
}
.panel-slide-enter-from,
.panel-slide-leave-to {
  transform: translateX(360px);
  opacity: 0;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 16px 12px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}

.panel-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.panel-icon {
  width: 34px;
  height: 34px;
  background: rgba(34, 211, 160, 0.1);
  border: 1px solid rgba(34, 211, 160, 0.25);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.panel-title {
  font-size: 14px;
  font-weight: 700;
  color: white;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.panel-subtitle {
  font-size: 10px;
  color: rgba(255,255,255,0.4);
  letter-spacing: 0.08em;
  margin-top: 1px;
}

.panel-close {
  width: 28px;
  height: 28px;
  background: rgba(255,255,255,0.06);
  border: none;
  border-radius: 6px;
  color: rgba(255,255,255,0.5);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  flex-shrink: 0;
}
.panel-close:hover {
  background: rgba(255,255,255,0.12);
  color: white;
}

.zone-summary {
  margin: 12px 16px 0;
  padding: 10px 12px;
  background: rgba(34, 211, 160, 0.05);
  border: 1px solid rgba(34, 211, 160, 0.15);
  border-radius: 8px;
}

.zone-summary-label {
  font-size: 11px;
  font-weight: 700;
  color: #22d3a0;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.zone-summary-info {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.zone-summary-info span {
  font-size: 10px;
  color: rgba(255,255,255,0.55);
  background: rgba(255,255,255,0.06);
  padding: 2px 7px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
}

.objects-summary {
  margin: 8px 16px 0;
  padding: 6px 10px;
  background: rgba(168, 139, 250, 0.08);
  border: 1px solid rgba(168, 139, 250, 0.2);
  border-radius: 6px;
  font-size: 11px;
  color: rgba(168, 139, 250, 0.8);
  display: flex;
  align-items: center;
  gap: 6px;
}

/* Predict button section */
.predict-section {
  padding: 16px;
}

.btn-predict {
  width: 100%;
  padding: 12px 14px;
  background: linear-gradient(135deg, rgba(34, 211, 160, 0.25), rgba(34, 211, 160, 0.15));
  border: 1px solid rgba(34, 211, 160, 0.5);
  border-radius: 8px;
  color: #22d3a0;
  font-size: 13px;
  font-family: 'Courier New', monospace;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.btn-predict:hover:not(.loading) {
  background: linear-gradient(135deg, rgba(34, 211, 160, 0.35), rgba(34, 211, 160, 0.22));
  box-shadow: 0 0 20px rgba(34, 211, 160, 0.3);
}

.btn-predict.loading {
  cursor: wait;
  opacity: 0.7;
}

.loading-dots {
  display: flex;
  gap: 3px;
}

.loading-dots span {
  animation: bounce 1s infinite;
  font-size: 18px;
  line-height: 1;
}
.loading-dots span:nth-child(2) { animation-delay: 0.15s; }
.loading-dots span:nth-child(3) { animation-delay: 0.30s; }

@keyframes bounce {
  0%, 100% { transform: translateY(0); opacity: 0.4; }
  50% { transform: translateY(-4px); opacity: 1; }
}

/* Comparison section */
.comparison-section {
  padding-bottom: 12px;
}

.panel-divider {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  margin: 12px 0 8px;
}

.panel-divider span {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: rgba(255,255,255,0.3);
  white-space: nowrap;
}

.panel-divider::before,
.panel-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: rgba(255,255,255,0.07);
}

.result-cards {
  display: flex;
  gap: 6px;
  padding: 0 16px;
}

.result-card {
  flex: 1;
  padding: 10px 8px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 8px;
  text-align: center;
}

.result-card.main {
  background: rgba(248, 113, 113, 0.06);
  border-color: rgba(248, 113, 113, 0.2);
}

.rc-label {
  display: block;
  font-size: 8px;
  color: rgba(255,255,255,0.4);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 4px;
}

.rc-value {
  font-size: 14px;
  font-weight: 700;
  color: white;
}

.rc-value.heat {
  color: #f87171;
  font-size: 16px;
}

.result-meta {
  display: flex;
  gap: 14px;
  padding: 8px 16px 0;
  font-size: 10px;
  color: rgba(255,255,255,0.35);
}

.result-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* Comparison list */
.comparison-list {
  padding: 0 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.comparison-row {
  padding: 8px 10px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 8px;
}

.cmp-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.cmp-header i {
  font-size: 10px;
  width: 12px;
  text-align: center;
}

.cmp-name {
  font-size: 10px;
  font-weight: 700;
  color: rgba(255,255,255,0.6);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.cmp-values {
  display: flex;
  align-items: center;
  gap: 8px;
}

.cmp-col {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.cmp-col.delta {
  margin-left: auto;
}

.cmp-label {
  font-size: 8px;
  color: rgba(255,255,255,0.3);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.cmp-val {
  font-size: 11px;
  font-weight: 700;
  color: rgba(255,255,255,0.7);
}

.cmp-val.positive {
  color: #4ade80;
}

.cmp-val.negative {
  color: #f87171;
}

.cmp-arrow {
  color: rgba(255,255,255,0.2);
  font-size: 10px;
  padding: 0 2px;
}

/* Post-actions */
.post-actions {
  padding: 12px 16px 0;
  display: flex;
  gap: 8px;
}

.btn-rerun {
  flex: 1;
  padding: 8px 14px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px;
  color: rgba(255,255,255,0.6);
  font-size: 11px;
  font-family: 'Courier New', monospace;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.btn-rerun:hover {
  background: rgba(34, 211, 160, 0.1);
  border-color: rgba(34, 211, 160, 0.3);
  color: #22d3a0;
}

/* Error */
.error-result {
  margin: 12px 16px 16px;
  padding: 12px;
  background: rgba(248, 113, 113, 0.05);
  border: 1px solid rgba(248, 113, 113, 0.2);
  border-radius: 8px;
  text-align: center;
}

.error-header {
  font-size: 11px;
  font-weight: 700;
  color: #f87171;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.error-msg {
  margin: 0 0 10px;
  font-size: 10px;
  color: rgba(248, 113, 113, 0.6);
  line-height: 1.4;
}

.result-fade-enter-active { transition: all 0.4s ease; }
.result-fade-enter-from { opacity: 0; transform: translateY(8px); }
</style>
