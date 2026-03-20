<template>
  <Transition name="panel-slide">
    <div v-if="visible" class="zone-info-panel" :style="panelStyle" v-show="!isHidden">

      <!-- Toolbar: drag handle + title + hide -->
      <div class="zip-toolbar">
        <div class="zip-drag" @mousedown.stop.prevent="startDrag" title="Drag to move">
          <i class="fas fa-ellipsis-vertical"></i>
        </div>
        <span class="zip-toolbar-title">
          <i class="fas fa-map-marked-alt"></i> Zone Analysis
        </span>
        <button class="zip-hide-btn" @click="isHidden = true" title="Hide panel">
          <i class="fas fa-chevron-right"></i>
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

      <!-- Loading state -->
      <div v-if="isLoading" class="loading-section">
        <div class="loading-spinner"></div>
        <span>Loading zone statistics...</span>
      </div>

      <!-- Error state -->
      <div v-else-if="loadError" class="error-section">
        <i class="fas fa-exclamation-triangle"></i>
        <span>{{ loadError }}</span>
        <button class="retry-btn" @click="fetchStats">Retry</button>
      </div>

      <!-- Real data -->
      <template v-else-if="stats">

        <!-- UHI Summary Cards (always visible) -->
        <div class="uhi-summary" v-if="stats.layer_stats['uhi']">
          <div class="uhi-card main">
            <span class="uhi-card-label">Mean UHI</span>
            <span class="uhi-card-value heat">{{ formatValue(stats.layer_stats['uhi'].mean, '') }}</span>
          </div>
          <div class="uhi-card">
            <span class="uhi-card-label">Min</span>
            <span class="uhi-card-value">{{ formatValue(stats.layer_stats['uhi'].min, '') }}</span>
          </div>
          <div class="uhi-card">
            <span class="uhi-card-label">Max</span>
            <span class="uhi-card-value">{{ formatValue(stats.layer_stats['uhi'].max, '') }}</span>
          </div>
        </div>

        <!-- Zone Points Toggle (collapsed by default) -->
        <button class="zip-dropdown-toggle" @click="showPoints = !showPoints">
          <i :class="showPoints ? 'fas fa-chevron-up' : 'fas fa-chevron-down'"></i>
          <span>Zone Points ({{ pointCount }})</span>
        </button>
        <div v-if="showPoints" class="zip-dropdown-body">
          <div class="zip-points-list" v-if="geometry?.geoJSON?.coordinates">
            <div v-for="(coord, i) in geometry.geoJSON.coordinates[0].slice(0, -1)" :key="i" class="zip-point-row">
              <span class="zip-point-idx">{{ i + 1 }}</span>
              <span class="zip-point-val">{{ coord[1].toFixed(5) }}, {{ coord[0].toFixed(5) }}</span>
            </div>
          </div>
          <div class="zip-points-list" v-else-if="geometry?.bounds">
            <div class="zip-point-row">
              <span class="zip-point-idx">NW</span>
              <span class="zip-point-val">{{ geometry.bounds.maxLat.toFixed(5) }}, {{ geometry.bounds.minLon.toFixed(5) }}</span>
            </div>
            <div class="zip-point-row">
              <span class="zip-point-idx">SE</span>
              <span class="zip-point-val">{{ geometry.bounds.minLat.toFixed(5) }}, {{ geometry.bounds.maxLon.toFixed(5) }}</span>
            </div>
          </div>
        </div>

        <!-- Detailed stats dropdown -->
        <button class="zip-dropdown-toggle" @click="showDetailedStats = !showDetailedStats">
          <i :class="showDetailedStats ? 'fas fa-chevron-up' : 'fas fa-chevron-down'"></i>
          <span>Input Layer Statistics</span>
        </button>
        <div v-if="showDetailedStats" class="zip-dropdown-body">
          <div class="stats-section">
            <div
              v-for="layer in displayLayers"
              :key="layer.key"
              class="layer-stat-card"
            >
              <div class="layer-stat-header">
                <i :class="layer.icon" :style="{ color: layer.color }"></i>
                <span class="layer-stat-name">{{ layer.label }}</span>
              </div>
              <div class="layer-stat-values" v-if="stats.layer_stats[layer.key]">
                <div class="layer-stat-item">
                  <span class="lsi-label">Mean</span>
                  <span class="lsi-value">{{ formatValue(stats.layer_stats[layer.key].mean, layer.unit) }}</span>
                </div>
                <div class="layer-stat-item">
                  <span class="lsi-label">Min</span>
                  <span class="lsi-value dim">{{ formatValue(stats.layer_stats[layer.key].min, layer.unit) }}</span>
                </div>
                <div class="layer-stat-item">
                  <span class="lsi-label">Max</span>
                  <span class="lsi-value dim">{{ formatValue(stats.layer_stats[layer.key].max, layer.unit) }}</span>
                </div>
                <div class="layer-stat-item">
                  <span class="lsi-label">Std</span>
                  <span class="lsi-value dim">{{ formatValue(stats.layer_stats[layer.key].std, layer.unit) }}</span>
                </div>
              </div>
              <div v-else class="layer-stat-na">No data</div>
            </div>
          </div>
        </div>

        <!-- Pixel count -->
        <div class="pixel-count">
          <i class="fas fa-th"></i>
          {{ stats.pixel_count.toLocaleString() }} valid pixels
        </div>

      </template>

    </div>
  </Transition>

  <!-- Mini restore button when hidden -->
  <button v-if="visible && isHidden" class="zip-restore-btn" @click="isHidden = false" title="Show Zone Analysis">
    <i class="fas fa-map-marked-alt"></i>
  </button>
</template>

<script setup>
  import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'

  const PREDICTION_URL = '/prediction'

  const props = defineProps({
    visible: { type: Boolean, default: false },
    geometry: { type: Object, default: null }
  })

  defineEmits(['close'])

  const isLoading = ref(false)
  const loadError = ref(null)
  const stats = ref(null)
  const isHidden = ref(false)
  const showDetailedStats = ref(false)
  const showPoints = ref(false)

  // Drag state
  const panelPos = ref({ x: -1, y: 70 })
  const isDragging = ref(false)
  let dragOffsetX = 0
  let dragOffsetY = 0

  const panelStyle = computed(() => {
    if (panelPos.value.x < 0) return { top: panelPos.value.y + 'px', right: '16px' }
    return { top: panelPos.value.y + 'px', left: panelPos.value.x + 'px', right: 'auto' }
  })

  function startDrag(e) {
    isDragging.value = true
    const el = e.target.closest('.zone-info-panel')
    const rect = el.getBoundingClientRect()
    if (panelPos.value.x < 0) panelPos.value.x = rect.left
    dragOffsetX = e.clientX - rect.left
    dragOffsetY = e.clientY - rect.top
  }

  function onMouseMove(e) {
    if (!isDragging.value) return
    panelPos.value.x = e.clientX - dragOffsetX
    panelPos.value.y = e.clientY - dragOffsetY
  }

  function stopDrag() {
    isDragging.value = false
  }

  onMounted(() => {
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', stopDrag)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', stopDrag)
  })

  const pointCount = computed(() => {
    if (props.geometry?.geoJSON?.coordinates) {
      return props.geometry.geoJSON.coordinates[0].length - 1
    }
    if (props.geometry?.bounds) return 4
    return 0
  })

  const displayLayers = [
    { key: 'ndvi',              label: 'NDVI',               icon: 'fas fa-leaf',                color: '#4ade80', unit: '' },
    { key: 'ndwi',              label: 'NDWI',               icon: 'fas fa-droplet',             color: '#38bdf8', unit: '' },
    { key: 'ndbi',              label: 'NDBI',               icon: 'fas fa-city',                color: '#94a3b8', unit: '' },
    { key: 'lst',               label: 'Land Surface Temp',  icon: 'fas fa-thermometer-half',    color: '#f87171', unit: '°C' },
    { key: 'dtm',               label: 'Elevation (DTM)',    icon: 'fas fa-mountain',            color: '#a78bfa', unit: 'm' },
    { key: 'dsm',               label: 'Surface Model (DSM)',icon: 'fas fa-mountain-sun',        color: '#c084fc', unit: 'm' },
    { key: 'building_height',   label: 'Building Height',    icon: 'fas fa-building',            color: '#f59e0b', unit: 'm' },
    { key: 'imperviousness',    label: 'Imperviousness',     icon: 'fas fa-road',                color: '#6b7280', unit: '' },
    { key: 'albedo',            label: 'Albedo',             icon: 'fas fa-sun',                 color: '#fbbf24', unit: '' },
    { key: 'distance_to_water', label: 'Dist. to Water',     icon: 'fas fa-water',               color: '#06b6d4', unit: 'm' },
    { key: 'distance_to_park',  label: 'Dist. to Park',      icon: 'fas fa-tree',                color: '#22c55e', unit: 'm' },
  ]

  function formatValue(val, unit) {
    if (val === null || val === undefined) return '—'
    const formatted = Math.abs(val) >= 100 ? val.toFixed(1) : val.toFixed(3)
    return unit ? `${formatted} ${unit}` : formatted
  }

  async function fetchStats() {
    console.log('test LOL')
    if (!props.geometry?.geoJSON) return

    console.log('Fetching stats for geometry:', props.geometry)
    isLoading.value = true
    loadError.value = null
    stats.value = null

    try {
      const resp = await fetch(`${PREDICTION_URL}/predict/zone/stats`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ geometry: props.geometry.geoJSON }),
      })
      if (!resp.ok) {
        const text = await resp.text()
        throw new Error(`${resp.status}: ${text}`)
      }
      stats.value = await resp.json()
    } catch (err) {
      console.error('Zone stats fetch failed:', err)
      loadError.value = err.message || 'Failed to load zone statistics'
    } finally {
      isLoading.value = false
    }
  }

  watch(
    () => [props.visible, props.geometry],
    ([vis, geom]) => {
      if (vis && geom?.geoJSON) {
        isHidden.value = false
        fetchStats()
      }
    },
    { immediate: true }
  )

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

  .panel-slide-enter-active,
  .panel-slide-leave-active {
    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s ease;
  }
  .panel-slide-enter-from,
  .panel-slide-leave-to {
    transform: translateX(340px);
    opacity: 0;
  }

  /* Toolbar */
  .zip-toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    background: rgba(34, 211, 160, 0.06);
    border-bottom: 1px solid rgba(34, 211, 160, 0.12);
  }

  .zip-drag {
    width: 20px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: grab;
    color: rgba(255, 255, 255, 0.35);
    border-radius: 4px;
    transition: all 0.15s;
    flex-shrink: 0;
  }
  .zip-drag:hover { color: rgba(255,255,255,0.7); background: rgba(255,255,255,0.06); }
  .zip-drag:active { cursor: grabbing; color: white; }

  .zip-toolbar-title {
    flex: 1;
    color: #22d3a0;
    font-size: 13px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .zip-hide-btn {
    width: 26px;
    height: 26px;
    background: rgba(255,255,255,0.06);
    border: none;
    border-radius: 6px;
    color: rgba(255,255,255,0.4);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    transition: all 0.15s;
    flex-shrink: 0;
  }
  .zip-hide-btn:hover { background: rgba(255,255,255,0.12); color: white; }

  /* Restore button */
  .zip-restore-btn {
    position: absolute;
    top: 70px;
    right: 16px;
    width: 36px;
    height: 36px;
    background: rgba(10, 14, 22, 0.95);
    border: 1px solid rgba(34, 211, 160, 0.25);
    border-radius: 8px;
    color: #22d3a0;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    z-index: 1500;
    transition: all 0.15s;
    box-shadow: 0 4px 16px rgba(0,0,0,0.4);
  }
  .zip-restore-btn:hover { background: rgba(34, 211, 160, 0.15); }

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

  /* UHI Summary Cards */
  .uhi-summary {
    display: flex;
    gap: 6px;
    padding: 12px 16px 0;
  }

  .uhi-card {
    flex: 1;
    padding: 10px 8px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px;
    text-align: center;
  }

  .uhi-card.main {
    background: rgba(248, 113, 113, 0.06);
    border-color: rgba(248, 113, 113, 0.2);
  }

  .uhi-card-label {
    display: block;
    font-size: 8px;
    color: rgba(255,255,255,0.4);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 4px;
  }

  .uhi-card-value {
    font-size: 14px;
    font-weight: 700;
    color: white;
  }

  .uhi-card-value.heat {
    color: #f87171;
    font-size: 16px;
  }

  /* Dropdown toggles */
  .zip-dropdown-toggle {
    display: flex;
    align-items: center;
    gap: 8px;
    width: calc(100% - 32px);
    margin: 8px 16px 0;
    padding: 8px 10px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 6px;
    color: rgba(255,255,255,0.5);
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    cursor: pointer;
    transition: all 0.15s;
    font-family: 'Courier New', monospace;
  }
  .zip-dropdown-toggle:hover {
    background: rgba(255,255,255,0.06);
    color: rgba(255,255,255,0.7);
  }
  .zip-dropdown-toggle i {
    font-size: 9px;
    width: 12px;
    text-align: center;
  }

  .zip-dropdown-body {
    margin: 0 16px;
    padding: 8px 0;
  }

  /* Points list */
  .zip-points-list {
    display: flex;
    flex-direction: column;
    gap: 3px;
    max-height: 120px;
    overflow-y: auto;
  }

  .zip-point-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 3px 8px;
    font-size: 10px;
  }

  .zip-point-idx {
    width: 20px;
    color: rgba(34, 211, 160, 0.6);
    font-weight: 700;
    flex-shrink: 0;
  }

  .zip-point-val {
    color: rgba(255,255,255,0.5);
    font-family: 'Courier New', monospace;
  }

  /* Loading */
  .loading-section {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    padding: 30px 16px;
    color: rgba(255,255,255,0.4);
    font-size: 11px;
  }

  .loading-spinner {
    width: 24px;
    height: 24px;
    border: 2px solid rgba(34, 211, 160, 0.2);
    border-top-color: #22d3a0;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .error-section {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    padding: 20px 16px;
    color: rgba(248, 113, 113, 0.7);
    font-size: 11px;
    text-align: center;
  }

  .retry-btn {
    padding: 6px 14px;
    background: rgba(248, 113, 113, 0.1);
    border: 1px solid rgba(248, 113, 113, 0.3);
    border-radius: 6px;
    color: #f87171;
    font-size: 11px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .retry-btn:hover { background: rgba(248, 113, 113, 0.2); }

  /* Detailed layer stats */
  .stats-section {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .layer-stat-card {
    padding: 8px 10px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px;
  }

  .layer-stat-header {
    display: flex;
    align-items: center;
    gap: 7px;
    margin-bottom: 6px;
  }

  .layer-stat-header i {
    font-size: 11px;
    width: 14px;
    text-align: center;
  }

  .layer-stat-name {
    font-size: 11px;
    font-weight: 700;
    color: rgba(255,255,255,0.7);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .layer-stat-values {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr 1fr;
    gap: 4px;
  }

  .layer-stat-item {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .lsi-label {
    font-size: 8px;
    color: rgba(255,255,255,0.3);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .lsi-value {
    font-size: 11px;
    font-weight: 700;
    color: white;
  }

  .lsi-value.dim {
    color: rgba(255,255,255,0.5);
    font-weight: 600;
  }

  .layer-stat-na {
    font-size: 10px;
    color: rgba(255,255,255,0.25);
    font-style: italic;
  }

  .pixel-count {
    padding: 8px 16px 16px;
    font-size: 10px;
    color: rgba(255,255,255,0.35);
    display: flex;
    align-items: center;
    gap: 6px;
  }
</style>
