<template>
  <Transition name="panel-slide">
    <div v-if="visible" class="zone-info-panel">

      <!-- Header -->
      <div class="panel-header">
        <div class="panel-header-left">
          <div class="panel-icon">
            <i class="fas fa-map-marked-alt"></i>
          </div>
          <div>
            <div class="panel-title">Zone Analysis</div>
            <div class="panel-subtitle">Current zone metrics</div>
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
          <span>N {{ geometry.bounds.maxLat.toFixed(4) }}</span>
          <span>S {{ geometry.bounds.minLat.toFixed(4) }}</span>
          <span>E {{ geometry.bounds.maxLon.toFixed(4) }}</span>
          <span>W {{ geometry.bounds.minLon.toFixed(4) }}</span>
        </div>
        <div class="zone-summary-info" v-else-if="geometry.summary">
          {{ geometry.summary.pointCount || geometry.summary.type }} &mdash;
          <span v-if="areaKm2">{{ areaKm2 }} km²</span>
        </div>
      </div>

      <!-- Divider: land cover -->
      <div class="panel-divider">
        <span>Land Cover Breakdown</span>
      </div>

      <div class="stats-section">
        <div class="stat-bar-row">
          <div class="stat-bar-label">
            <span class="stat-dot" style="background:#4ade80"></span>
            Vegetation
          </div>
          <div class="stat-bar-track">
            <div class="stat-bar-fill" style="width:34%; background:#4ade80"></div>
          </div>
          <span class="stat-bar-value">34%</span>
        </div>
        <div class="stat-bar-row">
          <div class="stat-bar-label">
            <span class="stat-dot" style="background:#94a3b8"></span>
            Impervious
          </div>
          <div class="stat-bar-track">
            <div class="stat-bar-fill" style="width:48%; background:#94a3b8"></div>
          </div>
          <span class="stat-bar-value">48%</span>
        </div>
        <div class="stat-bar-row">
          <div class="stat-bar-label">
            <span class="stat-dot" style="background:#f59e0b"></span>
            Buildings
          </div>
          <div class="stat-bar-track">
            <div class="stat-bar-fill" style="width:12%; background:#f59e0b"></div>
          </div>
          <span class="stat-bar-value">12%</span>
        </div>
        <div class="stat-bar-row">
          <div class="stat-bar-label">
            <span class="stat-dot" style="background:#38bdf8"></span>
            Water
          </div>
          <div class="stat-bar-track">
            <div class="stat-bar-fill" style="width:6%; background:#38bdf8"></div>
          </div>
          <span class="stat-bar-value">6%</span>
        </div>
      </div>

      <!-- Divider: climate metrics -->
      <div class="panel-divider">
        <span>Climate Metrics</span>
      </div>

      <div class="metrics-grid">
        <div class="metric-card">
          <div class="metric-icon"><i class="fas fa-thermometer-half"></i></div>
          <div class="metric-body">
            <span class="metric-value">28.4°C</span>
            <span class="metric-label">Mean Surface Temp</span>
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-icon hot"><i class="fas fa-temperature-arrow-up"></i></div>
          <div class="metric-body">
            <span class="metric-value">+3.1°C</span>
            <span class="metric-label">UHI Intensity</span>
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-icon green"><i class="fas fa-leaf"></i></div>
          <div class="metric-body">
            <span class="metric-value">0.31</span>
            <span class="metric-label">Mean NDVI</span>
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-icon blue"><i class="fas fa-droplet"></i></div>
          <div class="metric-body">
            <span class="metric-value">0.08</span>
            <span class="metric-label">Mean NDWI</span>
          </div>
        </div>
      </div>

      <!-- Divider: elevation -->
      <div class="panel-divider">
        <span>Elevation</span>
      </div>

      <div class="stats-section">
        <div class="elev-row">
          <div class="elev-item">
            <span class="elev-label">Min</span>
            <span class="elev-value">42 m</span>
          </div>
          <div class="elev-item">
            <span class="elev-label">Mean</span>
            <span class="elev-value">58 m</span>
          </div>
          <div class="elev-item">
            <span class="elev-label">Max</span>
            <span class="elev-value">74 m</span>
          </div>
        </div>
      </div>

      <!-- Divider: risk -->
      <div class="panel-divider">
        <span>Heat Risk Assessment</span>
      </div>

      <div class="risk-section">
        <div class="risk-badge high">
          <i class="fas fa-exclamation-triangle"></i>
          HIGH RISK
        </div>
        <p class="risk-desc">
          This zone shows elevated urban heat island effect due to high impervious surface ratio and low vegetation cover. Consider adding green infrastructure.
        </p>
      </div>

      <p class="mock-note">Data is for demonstration only. Connect to analysis API for real metrics.</p>

    </div>
  </Transition>
</template>

<script setup>
  import { computed } from 'vue'

  const props = defineProps({
    visible: { type: Boolean, default: false },
    geometry: { type: Object, default: null }
  })

  defineEmits(['close'])

  const areaKm2 = computed(() => {
    if (!props.geometry) return null
    if (props.geometry.type === 'boundingBox' && props.geometry.bounds) {
      const { minLon, maxLon, minLat, maxLat } = props.geometry.bounds
      const R = 6371
      const dLat = (maxLat - minLat) * Math.PI / 180
      const dLon = (maxLon - minLon) * Math.PI / 180
      const midLat = ((minLat + maxLat) / 2) * Math.PI / 180
      return (R * dLat * R * dLon * Math.cos(midLat)).toFixed(2)
    }
    if (props.geometry.type === 'polygon' && props.geometry.geoJSON) {
      const coords = props.geometry.geoJSON.coordinates[0]
      if (coords.length < 4) return null
      const R = 6371
      const toRad = (d) => d * Math.PI / 180
      let area = 0
      for (let i = 0; i < coords.length - 1; i++) {
        const [lon1, lat1] = coords[i]
        const [lon2, lat2] = coords[(i + 1) % (coords.length - 1)]
        area += toRad(lon2 - lon1) * (2 + Math.sin(toRad(lat1)) + Math.sin(toRad(lat2)))
      }
      return (Math.abs(area * R * R / 2)).toFixed(2)
    }
    return null
  })
</script>

<style scoped>
  .zone-info-panel {
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
    color: #22d3a0;
    font-size: 14px;
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
    font-size: 11px;
    color: rgba(255,255,255,0.55);
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
  }

  .zone-summary-info span {
    font-size: 10px;
    color: rgba(255,255,255,0.55);
    background: rgba(255,255,255,0.06);
    padding: 2px 7px;
    border-radius: 4px;
  }

  .panel-divider {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 16px;
    margin: 8px 0;
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

  /* Stat bars */
  .stats-section {
    padding: 0 16px 8px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .stat-bar-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .stat-bar-label {
    width: 90px;
    font-size: 10px;
    color: rgba(255,255,255,0.55);
    display: flex;
    align-items: center;
    gap: 5px;
    flex-shrink: 0;
  }

  .stat-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    display: inline-block;
    flex-shrink: 0;
  }

  .stat-bar-track {
    flex: 1;
    height: 5px;
    background: rgba(255,255,255,0.06);
    border-radius: 3px;
    overflow: hidden;
  }

  .stat-bar-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.4s ease;
  }

  .stat-bar-value {
    width: 32px;
    text-align: right;
    font-size: 10px;
    font-weight: 700;
    color: rgba(255,255,255,0.6);
    flex-shrink: 0;
  }

  /* Metrics grid */
  .metrics-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    padding: 0 16px 8px;
  }

  .metric-card {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px;
  }

  .metric-icon {
    width: 28px;
    height: 28px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    background: rgba(34, 211, 160, 0.1);
    color: #22d3a0;
    flex-shrink: 0;
  }
  .metric-icon.hot {
    background: rgba(248, 113, 113, 0.1);
    color: #f87171;
  }
  .metric-icon.green {
    background: rgba(74, 222, 128, 0.1);
    color: #4ade80;
  }
  .metric-icon.blue {
    background: rgba(56, 189, 248, 0.1);
    color: #38bdf8;
  }

  .metric-body {
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-width: 0;
  }

  .metric-value {
    font-size: 13px;
    font-weight: 700;
    color: white;
  }

  .metric-label {
    font-size: 8px;
    color: rgba(255,255,255,0.4);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    line-height: 1.3;
  }

  /* Elevation row */
  .elev-row {
    display: flex;
    justify-content: space-between;
    gap: 8px;
  }

  .elev-item {
    flex: 1;
    text-align: center;
    padding: 8px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 6px;
  }

  .elev-label {
    display: block;
    font-size: 9px;
    color: rgba(255,255,255,0.35);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 3px;
  }

  .elev-value {
    font-size: 13px;
    font-weight: 700;
    color: rgba(255,255,255,0.8);
  }

  /* Risk section */
  .risk-section {
    padding: 0 16px 8px;
  }

  .risk-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    border-radius: 6px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 8px;
  }

  .risk-badge.high {
    background: rgba(248, 113, 113, 0.12);
    border: 1px solid rgba(248, 113, 113, 0.3);
    color: #f87171;
  }

  .risk-badge.moderate {
    background: rgba(251, 191, 36, 0.12);
    border: 1px solid rgba(251, 191, 36, 0.3);
    color: #fbbf24;
  }

  .risk-badge.low {
    background: rgba(74, 222, 128, 0.12);
    border: 1px solid rgba(74, 222, 128, 0.3);
    color: #4ade80;
  }

  .risk-desc {
    margin: 0;
    font-size: 10px;
    color: rgba(255,255,255,0.4);
    line-height: 1.6;
  }

  .mock-note {
    margin: 8px 16px 16px;
    font-size: 9px;
    color: rgba(255,255,255,0.2);
    line-height: 1.4;
  }
</style>
