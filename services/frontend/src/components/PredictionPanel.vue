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
            <div class="panel-subtitle">Configure model parameters</div>
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

      <!-- Divider -->
      <div class="panel-divider">
        <span>Model Parameters</span>
      </div>

      <!-- Parameters -->
      <div class="params-list">

        <!-- Season -->
        <div class="param-group">
          <label class="param-label">
            <i class="fas fa-calendar-alt"></i>
            Season
          </label>
          <div class="param-toggle-group">
            <button
              v-for="s in seasons"
              :key="s.value"
              class="toggle-btn"
              :class="{ active: params.season === s.value }"
              @click="params.season = s.value"
            >{{ s.label }}</button>
          </div>
        </div>

        <!-- Time of day -->
        <div class="param-group">
          <label class="param-label">
            <i class="fas fa-clock"></i>
            Time of Day
          </label>
          <div class="param-toggle-group">
            <button
              v-for="t in timeOfDay"
              :key="t.value"
              class="toggle-btn"
              :class="{ active: params.timeOfDay === t.value }"
              @click="params.timeOfDay = t.value"
            >
              <i :class="t.icon" style="margin-right:4px; font-size:10px;"></i>
              {{ t.label }}
            </button>
          </div>
        </div>

        <!-- Temperature offset -->
        <div class="param-group">
          <label class="param-label">
            <i class="fas fa-thermometer-half"></i>
            Ambient Temperature
            <span class="param-value">{{ params.temperature }}°C</span>
          </label>
          <div class="slider-wrapper">
            <input
              type="range"
              class="param-slider"
              v-model.number="params.temperature"
              min="-5" max="45" step="1"
            />
            <div class="slider-track-fill" :style="{ width: sliderPercent(params.temperature, -5, 45) + '%' }"></div>
          </div>
          <div class="slider-labels">
            <span>-5°C</span>
            <span>45°C</span>
          </div>
        </div>

        <!-- Wind speed -->
        <div class="param-group">
          <label class="param-label">
            <i class="fas fa-wind"></i>
            Wind Speed
            <span class="param-value">{{ params.windSpeed }} m/s</span>
          </label>
          <div class="slider-wrapper">
            <input
              type="range"
              class="param-slider"
              v-model.number="params.windSpeed"
              min="0" max="20" step="0.5"
            />
            <div class="slider-track-fill" :style="{ width: sliderPercent(params.windSpeed, 0, 20) + '%' }"></div>
          </div>
          <div class="slider-labels">
            <span>0 m/s</span>
            <span>20 m/s</span>
          </div>
        </div>

        <!-- Vegetation density -->
        <div class="param-group">
          <label class="param-label">
            <i class="fas fa-leaf"></i>
            Vegetation Scenario
          </label>
          <div class="param-toggle-group">
            <button
              v-for="v in vegetationScenarios"
              :key="v.value"
              class="toggle-btn"
              :class="{ active: params.vegetation === v.value }"
              @click="params.vegetation = v.value"
            >{{ v.label }}</button>
          </div>
        </div>

        <!-- Urban density -->
        <div class="param-group">
          <label class="param-label">
            <i class="fas fa-city"></i>
            Urban Density Override
          </label>
          <div class="param-toggle-group">
            <button
              v-for="u in urbanDensity"
              :key="u.value"
              class="toggle-btn"
              :class="{ active: params.urbanDensity === u.value }"
              @click="params.urbanDensity = u.value"
            >{{ u.label }}</button>
          </div>
        </div>

      </div>

      <!-- Actions -->
      <div class="panel-actions">
        <button class="btn-reset" @click="resetParams">
          <i class="fas fa-undo"></i>
          Reset
        </button>
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

      <!-- Mock result -->
      <Transition name="result-fade">
        <div v-if="mockResult" class="mock-result">
          <div class="mock-result-header">
            <i class="fas fa-check-circle"></i>
            Prediction Complete
          </div>
          <div class="mock-result-body">
            <div class="mock-stat">
              <span class="mock-stat-label">Mean UHI Index</span>
              <span class="mock-stat-value heat">0.74</span>
            </div>
            <div class="mock-stat">
              <span class="mock-stat-label">Peak Temperature</span>
              <span class="mock-stat-value">+{{ (params.temperature + 3.2).toFixed(1) }}°C</span>
            </div>
            <div class="mock-stat">
              <span class="mock-stat-label">Risk Level</span>
              <span class="mock-stat-value warn">HIGH</span>
            </div>
          </div>
          <p class="mock-note">⚠️ This is a demonstration result. Real API not connected.</p>
        </div>
      </Transition>

    </div>
  </Transition>
</template>

<script setup>
import { ref, reactive } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  geometry: { type: Object, default: null }
})

const emit = defineEmits(['close', 'predict'])

const seasons = [
  { value: 'spring', label: 'Spring' },
  { value: 'summer', label: 'Summer' },
  { value: 'autumn', label: 'Autumn' },
  { value: 'winter', label: 'Winter' },
]

const timeOfDay = [
  { value: 'dawn', label: 'Dawn', icon: 'fas fa-cloud-sun' },
  { value: 'day', label: 'Day', icon: 'fas fa-sun' },
  { value: 'dusk', label: 'Dusk', icon: 'fas fa-cloud-moon' },
  { value: 'night', label: 'Night', icon: 'fas fa-moon' },
]

const vegetationScenarios = [
  { value: 'current', label: 'Current' },
  { value: 'low', label: 'Low' },
  { value: 'high', label: 'High' },
]

const urbanDensity = [
  { value: 'current', label: 'Current' },
  { value: 'dense', label: 'Dense' },
  { value: 'sparse', label: 'Sparse' },
]

const defaultParams = {
  season: 'summer',
  timeOfDay: 'day',
  temperature: 25,
  windSpeed: 3,
  vegetation: 'current',
  urbanDensity: 'current',
}

const params = reactive({ ...defaultParams })
const isLoading = ref(false)
const mockResult = ref(false)

function resetParams() {
  Object.assign(params, defaultParams)
  mockResult.value = false
}

async function launchPrediction() {
  isLoading.value = true
  mockResult.value = false
  // Simulate API call
  await new Promise(r => setTimeout(r, 1800))
  isLoading.value = false
  mockResult.value = true
  emit('predict', { geometry: props.geometry, params: { ...params } })
}

function sliderPercent(val, min, max) {
  return ((val - min) / (max - min)) * 100
}
</script>

<style scoped>
.prediction-panel {
  position: absolute;
  top: 70px;
  right: 16px;
  width: 320px;
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

/* Slide in from right */
.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s ease;
}
.panel-slide-enter-from,
.panel-slide-leave-to {
  transform: translateX(340px);
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
  margin: 12px 16px;
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

.panel-divider {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  margin: 4px 0 8px;
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

.params-list {
  padding: 0 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.param-group {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.param-label {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11px;
  font-weight: 600;
  color: rgba(255,255,255,0.6);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.param-label i {
  color: rgba(34, 211, 160, 0.7);
  font-size: 11px;
  width: 14px;
  text-align: center;
}

.param-value {
  margin-left: auto;
  font-size: 12px;
  color: #22d3a0;
  font-weight: 700;
}

.param-toggle-group {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.toggle-btn {
  flex: 1;
  min-width: 0;
  padding: 6px 4px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 6px;
  color: rgba(255,255,255,0.5);
  font-size: 10px;
  font-family: 'Courier New', monospace;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.toggle-btn:hover {
  background: rgba(34, 211, 160, 0.08);
  border-color: rgba(34, 211, 160, 0.3);
  color: rgba(255,255,255,0.8);
}

.toggle-btn.active {
  background: rgba(34, 211, 160, 0.15);
  border-color: rgba(34, 211, 160, 0.5);
  color: #22d3a0;
}

/* Slider */
.slider-wrapper {
  position: relative;
  height: 20px;
  display: flex;
  align-items: center;
}

.param-slider {
  width: 100%;
  height: 3px;
  -webkit-appearance: none;
  appearance: none;
  background: rgba(255,255,255,0.1);
  border-radius: 2px;
  outline: none;
  cursor: pointer;
  position: relative;
  z-index: 1;
}

.param-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #22d3a0;
  cursor: pointer;
  box-shadow: 0 0 8px rgba(34, 211, 160, 0.6);
  border: 2px solid rgba(0,0,0,0.4);
}

.slider-labels {
  display: flex;
  justify-content: space-between;
  font-size: 9px;
  color: rgba(255,255,255,0.25);
  margin-top: -2px;
}

/* Actions */
.panel-actions {
  display: flex;
  gap: 8px;
  padding: 16px 16px 12px;
  margin-top: 8px;
  border-top: 1px solid rgba(255,255,255,0.06);
}

.btn-reset {
  flex: 0 0 auto;
  padding: 10px 14px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px;
  color: rgba(255,255,255,0.5);
  font-size: 11px;
  font-family: 'Courier New', monospace;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  gap: 6px;
}

.btn-reset:hover {
  background: rgba(255,255,255,0.09);
  color: rgba(255,255,255,0.8);
}

.btn-predict {
  flex: 1;
  padding: 10px 14px;
  background: linear-gradient(135deg, rgba(34, 211, 160, 0.25), rgba(34, 211, 160, 0.15));
  border: 1px solid rgba(34, 211, 160, 0.5);
  border-radius: 8px;
  color: #22d3a0;
  font-size: 12px;
  font-family: 'Courier New', monospace;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
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

/* Mock result */
.mock-result {
  margin: 0 16px 16px;
  padding: 12px;
  background: rgba(34, 211, 160, 0.05);
  border: 1px solid rgba(34, 211, 160, 0.2);
  border-radius: 8px;
}

.result-fade-enter-active { transition: all 0.4s ease; }
.result-fade-enter-from { opacity: 0; transform: translateY(8px); }

.mock-result-header {
  font-size: 11px;
  font-weight: 700;
  color: #22d3a0;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.mock-result-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mock-stat {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
}

.mock-stat-label {
  color: rgba(255,255,255,0.5);
}

.mock-stat-value {
  font-weight: 700;
  color: white;
}

.mock-stat-value.heat { color: #f87171; }
.mock-stat-value.warn { color: #fbbf24; }

.mock-note {
  margin-top: 8px;
  font-size: 9px;
  color: rgba(255,255,255,0.25);
  line-height: 1.4;
  font-family: 'Courier New', monospace;
}
</style>