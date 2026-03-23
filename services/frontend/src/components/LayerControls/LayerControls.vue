<template>
  <div class="layer-panel" :style="panelStyle">
    <!-- DRAG HANDLE (separate from collapse) -->
    <div class="panel-toolbar">
      <div
        class="panel-drag-handle"
        @mousedown.stop.prevent="startDragPanel"
        title="Drag to move"
      >
        <i class="fas fa-ellipsis-vertical"></i>
      </div>
      <span class="panel-toolbar-title">Layers</span>
      <button class="panel-collapse-btn" @click="isPanelCollapsed = !isPanelCollapsed">
        <i :class="isPanelCollapsed ? 'fas fa-chevron-down' : 'fas fa-chevron-up'"></i>
      </button>
    </div>

    <div class="panel-content" v-show="!isPanelCollapsed">
      <!-- SWIPE MODE BANNER -->
      <div v-if="swipeEnabled" class="swipe-mode-banner">
        <i class="fas fa-arrows-left-right"></i>
        <span>Swipe Mode — Select layers for each side</span>
      </div>

      <!-- SECTION: URBAN HEAT ISLANDS -->
      <div class="layer-section">
        <button class="section-toggle" @click="sections.uhi = !sections.uhi">
          <h3 class="section-title">
            <i class="fas fa-temperature-high"></i>
            Urban Heat Islands
          </h3>
          <i :class="sections.uhi ? 'fas fa-chevron-up' : 'fas fa-chevron-down'" class="section-chevron"></i>
        </button>
        <Transition name="section-slide">
          <div v-show="sections.uhi" class="section-body">
            <div class="layer-list">
              <div
                v-for="layer in getLayersByCategory('uhi_maps')"
                :key="layer.id"
                class="layer-item"
                :class="{ active: swipeEnabled ? (swipeLeftLayerId === layer.id || swipeRightLayerId === layer.id) : layer.visible }"
              >
                <div class="layer-header">
                  <label v-if="!swipeEnabled" class="checkbox-wrapper">
                    <input type="checkbox" :checked="layer.visible" @change="$emit('toggle-layer', layer.id)" />
                    <span class="checkmark"></span>
                    <span class="layer-name">{{ layer.name }}</span>
                  </label>
                  <div v-else class="swipe-selector">
                    <span class="layer-name">{{ layer.name }}</span>
                    <div class="swipe-side-btns">
                      <button class="swipe-side-btn left" :class="{ active: swipeLeftLayerId === layer.id }" @click="$emit('set-swipe-left', layer.id)" title="Left side">L</button>
                      <button class="swipe-side-btn right" :class="{ active: swipeRightLayerId === layer.id }" @click="$emit('set-swipe-right', layer.id)" title="Right side">R</button>
                    </div>
                  </div>
                </div>
                <p class="layer-description">{{ layer.description }}</p>
                <!-- Per-layer action buttons -->
                <div class="layer-actions" v-if="layer.visible && !swipeEnabled">
                  <button class="layer-action-btn info" @click="$emit('layer-metadata', layer.id)" title="Zone Metadata">
                    <i class="fas fa-circle-info"></i> Info
                  </button>
                  <button class="layer-action-btn download" @click="$emit('layer-download', layer.id)" title="Download">
                    <i class="fas fa-download"></i> Download
                  </button>
                </div>
                <div class="opacity-control" v-if="layer.visible">
                  <label>Opacity: {{ Math.round(layer.opacity * 100) }}%</label>
                  <input type="range" min="0" max="1" step="0.1" :value="layer.opacity" @input="$emit('set-opacity', layer.id, parseFloat($event.target.value))" />
                </div>
                <div class="legend" v-if="layer.legend && layer.visible">
                  <div class="legend-gradient" :style="getLegendStyle(layer.legend)"></div>
                  <div class="legend-labels" v-if="tBase != null && uhiMin != null && uhiMax != null && layer.id === 'uhi_prediction'">
                    <span>{{ (tBase + uhiMin).toFixed(1) }} °C</span>
                    <span>{{ (tBase + uhiMax).toFixed(1) }} °C</span>
                  </div>
                  <div class="legend-labels" v-else>
                    <span>{{ layer.legend.min.label }}</span>
                    <span>{{ layer.legend.max.label }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- PREDICTION HISTORY (ephemeral) -->
            <div v-if="predictionHistory.length > 0" class="prediction-history">
              <div class="history-label">
                <i class="fas fa-clock-rotate-left"></i>
                Recent Predictions
              </div>
              <div
                v-for="entry in predictionHistory"
                :key="entry.id"
                class="history-item"
              >
                <div class="history-item-header">
                  <span class="history-date">{{ entry.date }}</span>
                  <span class="history-objects" v-if="entry.objectCount > 0">
                    <i class="fas fa-cubes"></i> {{ entry.objectCount }}
                  </span>
                </div>
                <div class="history-stats">
                  <div class="history-stat">
                    <span class="hs-label">Mean</span>
                    <span class="hs-value heat">{{ entry.stats.mean_uhi.toFixed(2) }}°C</span>
                  </div>
                  <div class="history-stat">
                    <span class="hs-label">Min</span>
                    <span class="hs-value">{{ entry.stats.min_uhi.toFixed(2) }}°C</span>
                  </div>
                  <div class="history-stat">
                    <span class="hs-label">Max</span>
                    <span class="hs-value">{{ entry.stats.max_uhi.toFixed(2) }}°C</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Transition>
      </div>

      <!-- SECTION: MAP LAYERS -->
      <div class="layer-section">
        <button class="section-toggle" @click="sections.mapLayers = !sections.mapLayers">
          <h3 class="section-title">
            <i class="fas fa-layer-group"></i>
            Map Layers
          </h3>
          <i :class="sections.mapLayers ? 'fas fa-chevron-up' : 'fas fa-chevron-down'" class="section-chevron"></i>
        </button>
        <Transition name="section-slide">
          <div v-show="sections.mapLayers" class="section-body">
            <div class="layer-list">
              <div
                v-for="layer in getLayersByCategory('map_layers')"
                :key="layer.id"
                class="layer-item"
                :class="{ active: swipeEnabled ? (swipeLeftLayerId === layer.id || swipeRightLayerId === layer.id) : layer.visible }"
              >
                <div class="layer-header">
                  <label v-if="!swipeEnabled" class="checkbox-wrapper">
                    <input type="checkbox" :checked="layer.visible" @change="$emit('toggle-layer', layer.id)" />
                    <span class="checkmark"></span>
                    <span class="layer-name">{{ layer.name }}</span>
                  </label>
                  <div v-else class="swipe-selector">
                    <span class="layer-name">{{ layer.name }}</span>
                    <div class="swipe-side-btns">
                      <button class="swipe-side-btn left" :class="{ active: swipeLeftLayerId === layer.id }" @click="$emit('set-swipe-left', layer.id)" title="Left side">L</button>
                      <button class="swipe-side-btn right" :class="{ active: swipeRightLayerId === layer.id }" @click="$emit('set-swipe-right', layer.id)" title="Right side">R</button>
                    </div>
                  </div>
                </div>
                <p class="layer-description">{{ layer.description }}</p>
                <!-- Per-layer action buttons -->
                <div class="layer-actions" v-if="layer.visible && !swipeEnabled">
                  <button class="layer-action-btn info" @click="$emit('layer-metadata', layer.id)" title="Zone Metadata">
                    <i class="fas fa-circle-info"></i> Info
                  </button>
                  <button class="layer-action-btn download" @click="$emit('layer-download', layer.id)" title="Download">
                    <i class="fas fa-download"></i> Download
                  </button>
                </div>
                <div class="opacity-control" v-if="layer.visible">
                  <label>Opacity: {{ Math.round(layer.opacity * 100) }}%</label>
                  <input type="range" min="0" max="1" step="0.1" :value="layer.opacity" @input="$emit('set-opacity', layer.id, parseFloat($event.target.value))" />
                </div>
                <div class="legend" v-if="layer.legend && layer.visible">
                  <div class="legend-gradient" :style="getLegendStyle(layer.legend)"></div>
                  <div class="legend-labels">
                    <span>{{ layer.legend.min.label }}</span>
                    <span>{{ layer.legend.max.label }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Transition>
      </div>

      <!-- SECTION: 3D TILESET -->
      <div class="layer-section">
        <button class="section-toggle" @click="sections.tileset = !sections.tileset">
          <h3 class="section-title">
            <i class="fas fa-cube"></i>
            3D Tileset
          </h3>
          <i :class="sections.tileset ? 'fas fa-chevron-up' : 'fas fa-chevron-down'" class="section-chevron"></i>
        </button>
        <Transition name="section-slide">
          <div v-show="sections.tileset" class="section-body">
            <div class="layer-list">
              <div class="layer-item" :class="{ active: buildingVisible }">
                <div class="layer-header">
                  <label class="checkbox-wrapper">
                    <input type="checkbox" :checked="buildingVisible" @change="$emit('toggle-buildings')" />
                    <span class="checkmark"></span>
                    <span class="layer-name">Buildings 3D</span>
                  </label>
                </div>
                <p class="layer-description">Interactive 3D building models snapped to terrain</p>
              </div>
              <div class="layer-item" :class="{ active: treeVisible }">
                <div class="layer-header">
                  <label class="checkbox-wrapper">
                    <input type="checkbox" :checked="treeVisible" @change="$emit('toggle-trees')" />
                    <span class="checkmark"></span>
                    <span class="layer-name">Trees 3D</span>
                  </label>
                </div>
                <p class="layer-description">Interactive 3D trees snapped to terrain</p>
              </div>
            </div>
          </div>
        </Transition>
      </div>

      <!-- SECTION: REAL TIME DATA (at bottom) -->
      <div class="layer-section">
        <button class="section-toggle" @click="sections.realtime = !sections.realtime">
          <h3 class="section-title">
            <i class="fas fa-satellite-dish"></i>
            Real Time
          </h3>
          <i :class="sections.realtime ? 'fas fa-chevron-up' : 'fas fa-chevron-down'" class="section-chevron"></i>
        </button>
        <Transition name="section-slide">
          <div v-show="sections.realtime" class="section-body">
            <div class="layer-list">
              <div class="layer-item" :class="{ active: showTempPanel }">
                <div class="layer-header">
                  <label class="checkbox-wrapper">
                    <input type="checkbox" :checked="showTempPanel" @change="$emit('toggle-temp-panel')" />
                    <span class="checkmark"></span>
                    <span class="layer-name">Live Temperature (VLINDER)</span>
                  </label>
                </div>
                <p class="layer-description">Show draggable panel with real-time T_base from VLINDER station</p>
                <div class="realtime-temp-preview" v-if="!showTempPanel">
                  <span class="temp-preview-value">{{ tBase != null ? tBase.toFixed(1) : '--' }} °C</span>
                </div>
              </div>
            </div>
          </div>
        </Transition>
      </div>
    </div>
  </div>
</template>

<script setup>
  import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
  import { useLayerControls } from './LayerControls.js'

  const props = defineProps({
    layers: { type: Array, required: true },
    activeLayers: { type: Array, default: () => [] },
    buildingVisible: { type: Boolean, default: true },
    treeVisible: { type: Boolean, default: false },
    swipeEnabled: { type: Boolean, default: false },
    swipeLeftLayerId: { type: String, default: null },
    swipeRightLayerId: { type: String, default: null },
    tBase: { type: Number, default: null },
    uhiMin: { type: Number, default: null },
    uhiMax: { type: Number, default: null },
    predictionHistory: { type: Array, default: () => [] },
    showTempPanel: { type: Boolean, default: false },
  })

  defineEmits([
    'toggle-layer', 'set-opacity', 'toggle-buildings', 'toggle-trees',
    'set-swipe-left', 'set-swipe-right', 'refresh-tbase',
    'toggle-temp-panel', 'layer-metadata', 'layer-download'
  ])

  const { getLegendStyle } = useLayerControls()

  const isPanelCollapsed = ref(false)

  const sections = reactive({
    uhi: true,
    mapLayers: false,
    tileset: false,
    realtime: true,
  })

  function getLayersByCategory(category) {
    return props.layers.filter(layer => layer.category === category)
  }

  // Drag state
  const panelPosition = ref({ x: 20, y: 100 })
  const isDraggingPanel = ref(false)
  let offsetX = 0
  let offsetY = 0

  const panelStyle = computed(() => ({
    left: panelPosition.value.x + 'px',
    top: panelPosition.value.y + 'px'
  }))

  function startDragPanel(e) {
    isDraggingPanel.value = true
    offsetX = e.clientX - panelPosition.value.x
    offsetY = e.clientY - panelPosition.value.y
  }

  function onMouseMove(e) {
    if (!isDraggingPanel.value) return
    panelPosition.value.x = e.clientX - offsetX
    panelPosition.value.y = e.clientY - offsetY
  }

  function stopDrag() {
    isDraggingPanel.value = false
  }

  function openRealtimeSection() {
    isPanelCollapsed.value = false
    sections.realtime = true
  }

  function openLayerSections() {
    isPanelCollapsed.value = false
    sections.uhi = true
    sections.mapLayers = true
  }

  defineExpose({ openRealtimeSection, openLayerSections })

  onMounted(() => {
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', stopDrag)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', stopDrag)
  })
</script>
<style src="./LayerControls.css"></style>
