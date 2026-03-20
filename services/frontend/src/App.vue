<template>
  <div class="app-container">
    <!-- NAVBAR -->
    <nav class="navbar">
      <div class="nav-left">
        <button
          class="nav-btn"
          :class="{ active: viewMode === '2D' }"
          @click="set2D"
          title="2D Map View"
        >
          <i class="fas fa-map"></i>
        </button>

        <button
          class="nav-btn"
          :class="{ active: viewMode === '3D' }"
          @click="set3D"
          title="3D Globe View"
        >
          <i class="fas fa-cube"></i>
        </button>

        <button
          class="nav-btn"
          :class="{ active: showLayers }"
          @click="toggleLayersPanel"
          title="Toggle Layers Panel"
        >
          <i class="fas fa-layer-group"></i>
        </button>

        <button
          class="nav-btn"
          :class="{ active: showToolbox }"
          @click="toggleToolbox"
          title="Toolbox"
        >
          <i class="fas fa-toolbox"></i>
        </button>

      </div>

      <div class="nav-center">
        <h1>🌡️ Brussels Urban Heat Island Monitor</h1>
      </div>

      <div class="nav-right">
        <button class="auth-btn">
          <i class="fas fa-user-plus"></i>
          Register
        </button>
        <button class="auth-btn">
          <i class="fas fa-right-to-bracket"></i>
          Login
        </button>
      </div>
    </nav>
    <!-- TOOLBOX MINI BAR -->
    <div v-if="showToolbox" class="toolbox-bar" :style="toolboxStyle">
      <div
        class="toolbox-handle"
        @mousedown="startDragToolbox"
      >
        <i class="fas fa-ellipsis-vertical"></i>
      </div>

      <div class="toolbox-divider"></div>

      <!-- PREDICT BUTTON WITH DROPDOWN MENU -->
      <div class="predict-container">
        <button
          class="tool-btn"
          title="Predict with drawing tools"
          @click="handlePredictClick"
          :class="{ active: showPredictMenu || isDrawingActive || showPredictionPanel}"
        >
          <i class="fas fa-magic"></i>
        </button>

        <!-- DROPDOWN MENU -->
        <div v-if="showPredictMenu" class="predict-menu">
          <button
            class="predict-menu-item"
            @click="startDrawingPolygon"
          >
            <i class="fas fa-draw-polygon"></i>
            Draw Polygon
          </button>
          <button
            class="predict-menu-item"
            @click="startDrawingBoundingBox"
          >
            <i class="fas fa-vector-square"></i>
            Draw Bounding Box
          </button>
        </div>
      </div>

      <button class="tool-btn" :class="{ active: swipeEnabled }" title="Swipe Content" @click="handleSwipeClick">
        <i class="fas fa-arrows-left-right"></i>
      </button>

      <div class="sun-sim-container">
        <button
          class="tool-btn"
          title="Sun Simulation"
          @click.stop="handleSunSimClick"
          :class="{ active: sunSimEnabled }"
        >
          <i class="fas fa-sun"></i>
        </button>

        <!-- SUN SIMULATION DROPDOWN PANEL -->
        <div v-if="showSunSimPanel" class="sun-sim-panel">
          <div class="sun-sim-header">
            <span class="sun-sim-title">
              <i class="fas fa-sun"></i> Sun Simulation
            </span>
          </div>

          <div class="sun-sim-body">
            <div class="sun-sim-time-display">
              <i class="fas fa-clock"></i>
              <span>{{ sunSimTimeFormatted }}</span>
            </div>

            <div class="sun-sim-slider-row">
              <span class="slider-label">00:00</span>
              <input
                type="range"
                min="0"
                max="1440"
                step="15"
                :value="sunSimTime"
                @input="setSunSimTime(Number($event.target.value))"
                class="sun-sim-slider"
              />
              <span class="slider-label">24:00</span>
            </div>

            <div class="sun-sim-presets">
              <button @click="setSunSimTime(360)">06:00</button>
              <button @click="setSunSimTime(540)">09:00</button>
              <button @click="setSunSimTime(720)">12:00</button>
              <button @click="setSunSimTime(900)">15:00</button>
              <button @click="setSunSimTime(1080)">18:00</button>
            </div>
          </div>
        </div>
      </div>
    </div>
    <!-- DRAWING HINT -->
    <Transition name="hint-fade">
      <div v-if="isDrawingActive" class="drawing-hint-banner">
        <div class="hint-main">
          <div class="hint-icon-pulse">
            <i class="fas fa-crosshairs"></i>
          </div>
          <div class="hint-instructions">
            <div class="hint-primary">
              <kbd>Left click</kbd> to add points · <kbd>Right click</kbd> to confirm
            </div>
            <div class="hint-secondary">
              <kbd>Ctrl+Z</kbd> undo last point · <kbd>Esc</kbd> cancel
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- ======================================== -->
    <!-- STEP 2 : SELECTION OVERLAY (SVG cutout) -->
    <!-- ======================================== -->
    <SelectionOverlay
      :visible="showSelectionOverlay"
      :geometry="activeGeometry"
      :cesiumViewer="cesiumViewerInstance"
      :viewMode="viewMode"
    />

    <!-- ======================================== -->
    <!-- WORKFLOW BOTTOM BAR        -->
    <!-- Appears after drawing, before prediction -->
    <!-- ======================================== -->
    <Transition name="bar-slide">
      <div v-if="showWorkflowBar" class="workflow-bar">
        <div
          class="workflow-step clickable"
          :class="{ done: workflowStep >= 1 }"
          @click="goToStep(1)"
          title="Back to zone & objects"
        >
          <div class="wf-num">1</div>
          <span>Zone Selected</span>
          <i class="fas fa-check-circle" v-if="workflowStep >= 1"></i>
        </div>
        <div class="wf-arrow">→</div>
        <div
          class="workflow-step clickable"
          :class="{ active: workflowStep === 1, done: workflowStep >= 2, optional: workflowStep < 2 }"
          @click="goToStep(1)"
          title="Place objects (optional)"
        >
          <div class="wf-num">2</div>
          <span>Place Objects</span>
          <span class="wf-optional-badge" v-if="workflowStep < 2">optional</span>
          <i class="fas fa-check-circle" v-if="workflowStep >= 2"></i>
        </div>
        <div class="wf-arrow">→</div>
        <div
          class="workflow-step clickable"
          :class="{ active: workflowStep === 2, done: workflowStep >= 3 }"
          @click="goToStep(2)"
          title="Go to prediction"
        >
          <div class="wf-num">3</div>
          <span>Predict</span>
          <i class="fas fa-check-circle" v-if="workflowStep >= 3"></i>
        </div>

        <div class="wf-actions">
          <button class="wf-btn secondary" @click="cancelWorkflow">
            <i class="fas fa-times"></i> Cancel
          </button>
          <button
            v-if="workflowStep === 1"
            class="wf-btn primary"
            @click="goToPredict"
          >
            <i class="fas fa-bolt"></i> Predict <i class="fas fa-arrow-right"></i>
          </button>
          <button
            v-if="workflowStep >= 2"
            class="wf-btn secondary"
            @click="backToObjects"
          >
            <i class="fas fa-arrow-left"></i> Back
          </button>
        </div>
      </div>
    </Transition>

    <!-- ======================================== -->
    <!-- TOOL MODAL (Metadata / Download)        -->
    <!-- ======================================== -->
    <Transition name="modal-fade">
      <div v-if="showToolModal && toolModalType === 'download'" class="tool-modal-overlay" @click.self="closeToolModal">
        <div class="tool-modal">
          <div class="tool-modal-header">
            <div class="tool-modal-icon download-icon">
              <i class="fas fa-download"></i>
            </div>
            <div>
              <h3 class="tool-modal-title">
                Download Data
                <span class="tool-modal-layer-badge" v-if="toolModalLayerName">{{ toolModalLayerName }}</span>
              </h3>
              <p class="tool-modal-subtitle">Download {{ toolModalLayerName || 'layer' }} as GeoTIFF</p>
            </div>
            <button class="tool-modal-close" @click="closeToolModal">
              <i class="fas fa-times"></i>
            </button>
          </div>
          <div class="tool-modal-options">
            <button class="tool-modal-card" @click="onToolModalChoice('boundingBox')">
              <i class="fas fa-vector-square"></i>
              <span class="tmc-label">Draw Bounding Box</span>
              <span class="tmc-desc">Select a rectangular zone to crop</span>
            </button>
            <button class="tool-modal-card" @click="onToolModalChoice('fullMap')">
              <i class="fas fa-globe"></i>
              <span class="tmc-label">Full Map</span>
              <span class="tmc-desc">Download entire {{ toolModalLayerName || 'layer' }}</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- LAYER INFO: Step 1 — choose region -->
    <Transition name="modal-fade">
      <div v-if="showLayerInfoChoice" class="tool-modal-overlay" @click.self="showLayerInfoChoice = false">
        <div class="tool-modal">
          <div class="tool-modal-header">
            <div class="tool-modal-icon">
              <i class="fas fa-circle-info"></i>
            </div>
            <div>
              <h3 class="tool-modal-title">
                Layer Statistics
                <span class="tool-modal-layer-badge" v-if="layerInfoName">{{ layerInfoName }}</span>
              </h3>
              <p class="tool-modal-subtitle">Choose the area to analyse</p>
            </div>
            <button class="tool-modal-close" @click="showLayerInfoChoice = false">
              <i class="fas fa-times"></i>
            </button>
          </div>
          <div class="tool-modal-options">
            <button class="tool-modal-card" @click="onInfoChoice('polygon')">
              <i class="fas fa-draw-polygon"></i>
              <span class="tmc-label">Draw Polygon</span>
              <span class="tmc-desc">Draw a custom zone</span>
            </button>
            <button class="tool-modal-card" @click="onInfoChoice('boundingBox')">
              <i class="fas fa-vector-square"></i>
              <span class="tmc-label">Draw Bounding Box</span>
              <span class="tmc-desc">Select a rectangular zone</span>
            </button>
            <button class="tool-modal-card" @click="onInfoChoice('fullMap')">
              <i class="fas fa-globe"></i>
              <span class="tmc-label">Full Map</span>
              <span class="tmc-desc">Statistics over the entire layer</span>
            </button>
          </div>
          <div class="tool-modal-warning">
            <i class="fas fa-clock"></i>
            <span>Large areas may take longer to compute.</span>
          </div>
        </div>
      </div>
    </Transition>

    <!-- LAYER INFO: Step 2 — results -->
    <Transition name="modal-fade">
      <div v-if="showLayerInfoResults" class="tool-modal-overlay" @click.self="closeLayerInfoResults">
        <div class="tool-modal layer-info-modal">
          <div class="tool-modal-header">
            <div class="tool-modal-icon">
              <i class="fas fa-circle-info"></i>
            </div>
            <div>
              <h3 class="tool-modal-title">
                Layer Statistics
                <span class="tool-modal-layer-badge" v-if="layerInfoName">{{ layerInfoName }}</span>
              </h3>
              <p class="tool-modal-subtitle">{{ layerInfoRegionLabel }}</p>
            </div>
            <button class="tool-modal-close" @click="closeLayerInfoResults">
              <i class="fas fa-times"></i>
            </button>
          </div>

          <!-- Loading state -->
          <div v-if="layerInfoLoading" class="layer-info-loading">
            <i class="fas fa-spinner fa-spin"></i>
            <span>Computing statistics...</span>
          </div>

          <!-- Error state -->
          <div v-else-if="layerInfoError" class="layer-info-error">
            <i class="fas fa-exclamation-triangle"></i>
            <span>{{ layerInfoError }}</span>
          </div>

          <!-- Stats cards -->
          <div v-else-if="layerInfoStats" class="layer-info-cards">
            <div class="layer-info-card">
              <span class="layer-info-card-label">Mean</span>
              <span class="layer-info-card-value">{{ layerInfoStats.mean }}</span>
            </div>
            <div class="layer-info-card">
              <span class="layer-info-card-label">Min</span>
              <span class="layer-info-card-value min">{{ layerInfoStats.min }}</span>
            </div>
            <div class="layer-info-card">
              <span class="layer-info-card-label">Max</span>
              <span class="layer-info-card-value max">{{ layerInfoStats.max }}</span>
            </div>
            <div class="layer-info-card">
              <span class="layer-info-card-label">Std Dev</span>
              <span class="layer-info-card-value std">{{ layerInfoStats.std }}</span>
            </div>
            <div class="layer-info-card wide">
              <span class="layer-info-card-label">Pixels</span>
              <span class="layer-info-card-value">{{ layerInfoStats.pixel_count?.toLocaleString() }}</span>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- ======================================== -->
    <!-- DOWNLOAD CONFIRM DIALOG                 -->
    <!-- ======================================== -->
    <Transition name="modal-fade">
      <div v-if="showDownloadConfirm" class="tool-modal-overlay" @click.self="showDownloadConfirm = false">
        <div class="tool-modal confirm-modal">
          <div class="tool-modal-header">
            <div class="tool-modal-icon download-icon">
              <i class="fas fa-download"></i>
            </div>
            <div>
              <h3 class="tool-modal-title">Confirm Download</h3>
              <p class="tool-modal-subtitle">{{ downloadConfirmText }}</p>
            </div>
          </div>
          <div class="confirm-actions">
            <button class="confirm-btn cancel" @click="showDownloadConfirm = false">
              <i class="fas fa-times"></i> Cancel
            </button>
            <button class="confirm-btn proceed" @click="executeDownload">
              <i class="fas fa-download"></i> Download
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- ======================================== -->
    <!-- ZONE OBJECTS PANEL (drag & drop 3D)     -->
    <!-- ======================================== -->
    <ZoneObjectsPanel
      :visible="showZoneObjectsPanel"
      :geometry="activeGeometry"
      :cesiumViewer="cesiumViewerInstance"
      @objects-changed="onZoneObjectsChanged"
    />

    <!-- ======================================== -->
    <!-- ZONE INFO PANEL (right side, zone data) -->
    <!-- ======================================== -->
    <ZoneInfoPanel
      :visible="showZoneInfoPanel"
      :geometry="activeGeometry"
      ref="zoneInfoPanelRef"
    />

    <!-- ======================================== -->
    <!-- PREDICTION PANEL (replaces info panel)  -->
    <!-- ======================================== -->
    <PredictionPanel
      :visible="showPredictionPanel"
      :geometry="activeGeometry"
      :zoneObjects="zoneObjects"
      :zoneStats="zoneStatsData"
      @close="closePredictionPanel"
      @predict="onPredict"
    />

    <!-- 3D VIEWER -->
    <CesiumViewer
      ref="cesiumViewerRef"
      :layers="layers"
      :activeLayers="activeLayers"
      :viewMode="viewMode"
      :buildingVisible="buildingVisible"
      :treeVisible="treeVisible"
      :drawingMode="drawingMode"
      :swipeEnabled="swipeEnabled"
      :swipePosition="swipePosition"
      :swipeLeftLayerId="swipeLeftLayerId"
      :swipeRightLayerId="swipeRightLayerId"
      :sunSimEnabled="sunSimEnabled"
      :sunSimTime="sunSimTime"
      :tBase="tBase"
      :uhiMin="uhiMin"
      :uhiMax="uhiMax"
      :predictionOverlay="predictionOverlay"
      @geometry-drawn="onGeometryDrawnRouter"
      @drawing-active="onDrawingActive"
      @pixel-click="onPixelClick"
    />

    <!-- PIXEL INFO PANEL (click on map) -->
    <PixelInfoPanel
      :visible="showPixelInfo"
      :pixelData="pixelData"
      :isLoading="pixelLoading"
      :screenX="pixelScreenX"
      :screenY="pixelScreenY"
      @close="showPixelInfo = false"
    />

    <!-- SWIPE DIVIDER -->
    <div
      v-if="swipeEnabled"
      class="swipe-divider"
      :style="{ left: (swipePosition * 100) + '%' }"
    >
      <div class="swipe-handle" @mousedown.prevent.stop="startSwipeDrag">
        <i class="fas fa-grip-lines-vertical"></i>
      </div>
    </div>

    <!-- LAYER CONTROLS PANEL -->
    <LayerControls
      v-if="showLayers"
      ref="layerControlsRef"
      :layers="layers"
      :activeLayers="activeLayers"
      :buildingVisible="buildingVisible"
      :treeVisible="treeVisible"
      :swipeEnabled="swipeEnabled"
      :swipeLeftLayerId="swipeLeftLayerId"
      :swipeRightLayerId="swipeRightLayerId"
      :tBase="tBase"
      :uhiMin="uhiMin"
      :uhiMax="uhiMax"
      :predictionHistory="predictionHistory"
      :showTempPanel="showTempPanel"
      @toggle-layer="toggleLayer"
      @set-opacity="setOpacity"
      @toggle-buildings="toggleBuildings"
      @toggle-trees="toggleTrees"
      @set-swipe-left="onSetSwipeLeft"
      @set-swipe-right="onSetSwipeRight"
      @refresh-tbase="fetchTBase"
      @toggle-temp-panel="showTempPanel = !showTempPanel"
      @layer-metadata="onLayerMetadata"
      @layer-download="onLayerDownload"
    />

    <!-- DRAGGABLE TEMPERATURE PANEL -->
    <div v-if="showTempPanel" class="temp-panel" :style="tempPanelStyle">
      <div class="temp-panel-toolbar">
        <div
          class="temp-panel-drag"
          @mousedown.stop.prevent="startDragTempPanel"
        >
          <i class="fas fa-ellipsis-vertical"></i>
        </div>
        <span class="temp-panel-title">
          <i class="fas fa-thermometer-half" style="color: #4ade80;"></i>
          Live Temperature
        </span>
        <button class="temp-panel-close" @click="showTempPanel = false">
          <i class="fas fa-times"></i>
        </button>
      </div>
      <div class="temp-panel-body">
        <div class="temp-panel-value">
          <span class="temp-big">{{ tBase != null ? tBase.toFixed(1) : '--' }}</span>
          <span class="temp-unit">°C</span>
        </div>
        <div class="temp-panel-source">
          <i class="fas fa-satellite-dish"></i>
          VLINDER Station
        </div>
        <button class="temp-panel-refresh" @click="fetchTBase" title="Refresh">
          <i class="fas fa-sync-alt"></i> Refresh
        </button>
        <div class="temp-panel-hint">
          Baseline ambient temperature (T_base) used for UHI predictions.
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
  import { useAppState } from './App.js'
  import CesiumViewer from './components/CesiumViewer.vue'
  import LayerControls from './components/LayerControls.vue'
  import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
  import SelectionOverlay from './components/SelectionOverlay.vue'
  import PredictionPanel from './components/PredictionPanel.vue'
  import ZoneObjectsPanel from './components/ZoneObjectsPanel.vue'
  import ZoneInfoPanel from './components/ZoneInfoPanel.vue'
  import PixelInfoPanel from './components/PixelInfoPanel.vue'
  const {
    viewMode, showLayers, layers, activeLayers, buildingVisible, treeVisible,
    showToolbox, drawingMode, showPredictMenu, drawnGeometries,
    set2D, set3D, toggleLayersPanel, toggleLayer, setOpacity,
    toggleBuildings, toggleTrees, toggleToolbox, togglePredictMenu,
    startDrawingPolygon, startDrawingBoundingBox, stopDrawing, addGeometry,
    swipeEnabled, swipeLeftLayerId, swipeRightLayerId, swipePosition, toggleSwipe,
    sunSimEnabled, sunSimTime, toggleSunSim, setSunSimTime
  } = useAppState()
  
  const cesiumViewerRef = ref(null)
  const cesiumViewerInstance = computed(() =>
    cesiumViewerRef.value?.getViewer?.() ?? null
  )

  // T_base + UHI range state
  const tBase = ref(15.0)
  const layerControlsRef = ref(null)
  const uhiMin = ref(null)
  const uhiMax = ref(null)

  async function fetchUhiRange() {
    try {
      const ORION_URL = window.location.port === '5173' ? '/orion' : '/orion'
      const entityId = 'urn:ngsi-ld:UHIHeatMap:XGBoost:brussels:2024'
      const resp = await fetch(
        `${ORION_URL}/ngsi-ld/v1/entities/${entityId}?local=true`,
        { headers: { 'Accept': 'application/json' } }
      )
      if (!resp.ok) return
      const entity = await resp.json()
      const range = entity?.valueRange?.value
      if (range) {
        uhiMin.value = range.min
        uhiMax.value = range.max
      }
    } catch (err) {
      console.warn('Failed to fetch UHI range from Orion:', err)
    }
  }

  const VLINDER_URL = '/prediction'

  async function fetchTBase() {
    try {
      const resp = await fetch(`${VLINDER_URL}/vlinder/t_base`)
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data = await resp.json()
      tBase.value = data.value
    } catch (err) {
      console.warn('VLINDER fetch failed:', err)
    }
  }

  // TEMPERATURE PANEL STATE
  const showTempPanel = ref(false)
  const tempPanelPosition = ref({ x: window.innerWidth - 260, y: 100 })
  const isDraggingTempPanel = ref(false)
  let tempOffsetX = 0
  let tempOffsetY = 0

  const tempPanelStyle = computed(() => ({
    left: tempPanelPosition.value.x + 'px',
    top: tempPanelPosition.value.y + 'px'
  }))

  function startDragTempPanel(e) {
    isDraggingTempPanel.value = true
    tempOffsetX = e.clientX - tempPanelPosition.value.x
    tempOffsetY = e.clientY - tempPanelPosition.value.y
  }

  // TOOLBOX DRAG STATE
  const toolboxPosition = ref({
    x: window.innerWidth / 2 - 200,
    y: 90
  })

  const isDraggingToolbox = ref(false)
  let offsetX = 0
  let offsetY = 0

  const toolboxStyle = computed(() => ({
    left: toolboxPosition.value.x + 'px',
    top: toolboxPosition.value.y + 'px'
  }))

  function startDragToolbox(e) {
    isDraggingToolbox.value = true
    offsetX = e.clientX - toolboxPosition.value.x
    offsetY = e.clientY - toolboxPosition.value.y
  }

  function onMouseMove(e) {
    if (isDraggingToolbox.value) {
      toolboxPosition.value.x = e.clientX - offsetX
      toolboxPosition.value.y = e.clientY - offsetY
    }
    if (isDraggingTempPanel.value) {
      tempPanelPosition.value.x = e.clientX - tempOffsetX
      tempPanelPosition.value.y = e.clientY - tempOffsetY
    }
    if (isSwipeDragging.value) {
      swipePosition.value = Math.max(0.05, Math.min(0.95, e.clientX / window.innerWidth))
    }
  }

  function onClickOutside(e) {
    const toolbox = document.querySelector('.toolbox-bar')
    if (toolbox && !toolbox.contains(e.target)) {
      showPredictMenu.value = false
      showSunSimPanel.value = false
    }
  }

  function stopDrag() {
    isDraggingToolbox.value = false
    isDraggingTempPanel.value = false
    if (isSwipeDragging.value) {
      isSwipeDragging.value = false
      document.body.style.cursor = ''
    }
  }

  // ========================================
  // DRAWING STATE
  // ========================================
  const isDrawingActive = ref(false)

  function onDrawingActive(active) {
    isDrawingActive.value = active
  }

  // Auto-switch to 2D when drawing starts
  watch(drawingMode, (mode) => {
    if (mode && viewMode.value !== '2D') set2D()
  })

  // ========================================
  // WORKFLOW LOCK (blocks 3D during steps 1-3)
  // ========================================
  const isWorkflowActive = computed(
    () => isDrawingActive.value || showWorkflowBar.value
  )

  // ========================================
  // SWIPE STATE (local UI)
  // ========================================
  const isSwipeDragging = ref(false)

  // Predict menu click handler
  function handlePredictClick() {
    if (!showPredictMenu.value) deactivateToolsExcept('predict')
    togglePredictMenu()
  }

  // Deactivate other toolbox tools for mutual exclusivity
  function deactivateToolsExcept(keepTool) {
    if (keepTool !== 'swipe' && swipeEnabled.value) {
      toggleSwipe() // turns off swipe
    }
    if (keepTool !== 'sunSim' && sunSimEnabled.value) {
      toggleSunSim()
      showSunSimPanel.value = false
    }
    if (keepTool !== 'predict') {
      showPredictMenu.value = false
    }
  }

  function handleSwipeClick() {
    const wasEnabled = swipeEnabled.value
    if (!wasEnabled) deactivateToolsExcept('swipe')
    toggleSwipe()
    if (swipeEnabled.value) {
      if (!showLayers.value) showLayers.value = true
      // Auto-expand layer sections so user can pick L/R layers
      nextTick(() => {
        layerControlsRef.value?.openLayerSections()
      })
    }
  }

  function onSetSwipeLeft(layerId) {
    swipeLeftLayerId.value = swipeLeftLayerId.value === layerId ? null : layerId
  }

  function onSetSwipeRight(layerId) {
    swipeRightLayerId.value = swipeRightLayerId.value === layerId ? null : layerId
  }

  function startSwipeDrag(e) {
    isSwipeDragging.value = true
    document.body.style.cursor = 'ew-resize'
    e.preventDefault()
  }

  // ========================================
  // SUN SIMULATION (local UI)
  // ========================================
  const showSunSimPanel = ref(false)

  function handleSunSimClick() {
    const wasEnabled = sunSimEnabled.value
    if (!wasEnabled) deactivateToolsExcept('sunSim')
    toggleSunSim()
    showSunSimPanel.value = !wasEnabled
  }

  const sunSimTimeFormatted = computed(() => {
    const hours = Math.floor(sunSimTime.value / 60)
    const mins = sunSimTime.value % 60
    return `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`
  })

  // Auto-switch to 3D when sun sim is enabled
  watch(sunSimEnabled, (enabled) => {
    if (enabled && viewMode.value !== '3D') set3D()
  })

  // ========================================
  // WORKFLOW STATE  (Step 1 → 2 → 3)
  // ========================================
  const activeGeometry = ref(null)       // geometry from drawing
  const showSelectionOverlay = ref(false) // SVG overlay
  const showWorkflowBar = ref(false)      // bottom bar guiding user
  const showPredictionPanel = ref(false)  // Prediction panel
  const workflowStep = ref(0)             // 0=none, 1=objects, 2=predict, 3=done
  const showZoneObjectsPanel = ref(false) // Zone objects drag-and-drop panel
  const showZoneInfoPanel = ref(false)    // Zone info/data panel (right side)
  const zoneObjects = ref([])             // placed 3D objects
  const predictionOverlay = ref(null)     // {image_base64, bounds} for Cesium overlay
  const zoneInfoPanelRef = ref(null)      // ref to ZoneInfoPanel
  const zoneStatsData = ref(null)         // zone stats from ZoneInfoPanel for comparison


  function onGeometryDrawnPredict(geometry) {
    addGeometry(geometry)
    stopDrawing()
    activeGeometry.value = geometry
    showSelectionOverlay.value = true
    showWorkflowBar.value = true
    workflowStep.value = 1
    // Auto-open side panels: objects (left) + info (right)
    showZoneObjectsPanel.value = true
    showZoneInfoPanel.value = true
    showPredictionPanel.value = false
    // Switch to 3D to visualize the zone
    if (viewMode.value !== '3D') set3D()
  }

  // Navigate to a specific workflow step
  function goToStep(step) {
    if (step === 1) {
      backToObjects()
    } else if (step === 2) {
      goToPredict()
    }
  }

  // Go to predict step: open prediction panel, hide info panel
  function goToPredict() {
    workflowStep.value = 2
    showPredictionPanel.value = true
    showZoneInfoPanel.value = false
  }

  // Back from prediction to objects step
  function backToObjects() {
    workflowStep.value = 1
    showPredictionPanel.value = false
    showZoneInfoPanel.value = true
  }

  // Close prediction panel
  function closePredictionPanel() {
    showPredictionPanel.value = false
    workflowStep.value = 1
    showZoneInfoPanel.value = true
  }

  // Cancel entire workflow
  function cancelWorkflow() {
    showSelectionOverlay.value = false
    showWorkflowBar.value = false
    showPredictionPanel.value = false
    showZoneObjectsPanel.value = false
    showZoneInfoPanel.value = false
    workflowStep.value = 0
    activeGeometry.value = null
    zoneObjects.value = []
    predictionOverlay.value = null
    zoneStatsData.value = null
  }

  function onZoneObjectsChanged(objects) {
    zoneObjects.value = objects
  }

  // Called when prediction panel emits 'predict'
  function onPredict(payload) {
    if (payload.result) {
      predictionOverlay.value = {
        image_base64: payload.result.image_base64,
        bounds: payload.result.bounds,
        stats: payload.result.stats,
      }
      workflowStep.value = 3

      // Save to ephemeral prediction history
      predictionHistory.value.unshift({
        id: Date.now(),
        date: new Date().toLocaleString(),
        stats: payload.result.stats,
        objectCount: zoneObjects.value.length,
      })
    }
  }

  // ========================================
  // PIXEL INFO (click on map)
  // ========================================
  const PREDICTION_URL = '/prediction'
  const showPixelInfo = ref(false)
  const pixelData = ref(null)
  const pixelLoading = ref(false)
  const pixelScreenX = ref(0)
  const pixelScreenY = ref(0)

  async function onPixelClick({ lon, lat, screenX, screenY }) {
    // Don't show pixel info during workflows
    if (isWorkflowActive.value || downloadMode.value) return

    pixelScreenX.value = screenX
    pixelScreenY.value = screenY
    showPixelInfo.value = true
    pixelLoading.value = true
    pixelData.value = { lon, lat, values: {} }

    try {
      const resp = await fetch(`${PREDICTION_URL}/predict/pixel/value`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lon, lat }),
      })
      if (!resp.ok) throw new Error(`${resp.status}`)
      const data = await resp.json()
      pixelData.value = data
    } catch (err) {
      console.error('Pixel value fetch failed:', err)
      pixelData.value = { lon, lat, values: {} }
    } finally {
      pixelLoading.value = false
    }
  }

  // ========================================
  // TOOL MODAL (Metadata / Download) — per-layer
  // ========================================
  const showToolModal = ref(false)
  const toolModalType = ref('download')
  const toolModalLayerId = ref(null) // e.g. 'ndvi', 'uhi_prediction'
  const downloadMode = ref(false)
  const activeDownloadLayer = ref(null) // layer id for download

  // Backend layer name mapping
  const backendLayerMap = {
    'uhi_prediction': 'uhi',
  }
  function toBackendLayer(frontendId) {
    return backendLayerMap[frontendId] || frontendId
  }

  const toolModalLayerName = computed(() => {
    if (!toolModalLayerId.value) return null
    const layer = layers.find(l => l.id === toolModalLayerId.value)
    return layer ? layer.name : toolModalLayerId.value
  })

  // ── LAYER INFO (stats) — 2-step: choose region → show results ──
  const showLayerInfoChoice = ref(false)
  const showLayerInfoResults = ref(false)
  const layerInfoLoading = ref(false)
  const layerInfoError = ref(null)
  const layerInfoStats = ref(null)
  const layerInfoName = ref(null)
  const layerInfoLayerId = ref(null)
  const layerInfoRegionLabel = ref('Full raster')
  const infoMode = ref(false)  // true when drawing geometry for info

  function onLayerMetadata(layerId) {
    const layer = layers.find(l => l.id === layerId)
    layerInfoName.value = layer ? layer.name : layerId
    layerInfoLayerId.value = layerId
    layerInfoStats.value = null
    layerInfoError.value = null
    showLayerInfoChoice.value = true
  }

  function onInfoChoice(choice) {
    showLayerInfoChoice.value = false
    if (choice === 'fullMap') {
      layerInfoRegionLabel.value = 'Full raster'
      fetchLayerStats(null)
    } else if (choice === 'boundingBox') {
      infoMode.value = true
      startDrawingBoundingBox()
    } else if (choice === 'polygon') {
      infoMode.value = true
      startDrawingPolygon()
    }
  }

  async function fetchLayerStats(geometry) {
    layerInfoLoading.value = true
    layerInfoStats.value = null
    layerInfoError.value = null
    showLayerInfoResults.value = true
    try {
      const backendLayer = toBackendLayer(layerInfoLayerId.value)
      const body = { layer: backendLayer }
      if (geometry) body.geometry = geometry
      const resp = await fetch(`${PREDICTION_URL}/predict/layer/stats`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!resp.ok) throw new Error(`Server error: ${resp.status}`)
      layerInfoStats.value = await resp.json()
    } catch (err) {
      console.error('Layer stats fetch failed:', err)
      layerInfoError.value = err.message || 'Failed to load layer statistics'
    } finally {
      layerInfoLoading.value = false
    }
  }

  function closeLayerInfoResults() {
    showLayerInfoResults.value = false
  }

  // ── DOWNLOAD MODAL ──
  function onLayerDownload(layerId) {
    toolModalType.value = 'download'
    toolModalLayerId.value = layerId
    showToolModal.value = true
  }

  function closeToolModal() {
    showToolModal.value = false
    toolModalLayerId.value = null
  }

  function onToolModalChoice(choice) {
    const layerId = toolModalLayerId.value
    closeToolModal()

    activeDownloadLayer.value = layerId
    if (choice === 'fullMap') {
      pendingDownloadGeometry.value = null
      const layerObj = layers.find(l => l.id === layerId)
      const name = layerObj ? layerObj.name : layerId
      downloadConfirmText.value = `Download the full ${name} layer as GeoTIFF?`
      showDownloadConfirm.value = true
    } else {
      downloadMode.value = true
      startDrawingBoundingBox()
    }
  }

  // ========================================
  // DOWNLOAD WITH VALIDATION
  // ========================================
  const showDownloadConfirm = ref(false)
  const downloadConfirmText = ref('')
  const pendingDownloadGeometry = ref(null)
  const isDownloading = ref(false)

  async function executeDownload() {
    showDownloadConfirm.value = false
    isDownloading.value = true
    const geometry = pendingDownloadGeometry.value
    const layerId = activeDownloadLayer.value || 'uhi'
    const backendLayer = toBackendLayer(layerId)
    const fileName = geometry ? `${backendLayer}_crop.tif` : `${backendLayer}_full.tif`

    try {
      const resp = await fetch(`${PREDICTION_URL}/predict/download`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ layer: backendLayer, geometry: geometry }),
      })
      if (!resp.ok) throw new Error(`Download failed: ${resp.status}`)
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = fileName
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Download failed:', err)
    } finally {
      isDownloading.value = false
      pendingDownloadGeometry.value = null
      activeDownloadLayer.value = null
    }
  }

  // ========================================
  // PREDICTION HISTORY (ephemeral, in-memory)
  // ========================================
  const predictionHistory = ref([])

  // ========================================
  // GEOMETRY DRAWN HANDLER (routes to correct mode)
  // ========================================
  function onGeometryDrawnRouter(geometry) {
    if (downloadMode.value) {
      // Download mode: show confirm dialog with zone info
      addGeometry(geometry)
      stopDrawing()
      downloadMode.value = false
      pendingDownloadGeometry.value = geometry.geoJSON
      const layerObj = layers.find(l => l.id === activeDownloadLayer.value)
      const name = layerObj ? layerObj.name : (activeDownloadLayer.value || 'layer')
      downloadConfirmText.value = `Download the selected ${name} zone as GeoTIFF?`
      showDownloadConfirm.value = true
      return
    }

    if (infoMode.value) {
      // Info mode: fetch stats for the drawn geometry
      addGeometry(geometry)
      stopDrawing()
      infoMode.value = false
      layerInfoRegionLabel.value = 'Selected zone'
      fetchLayerStats(geometry.geoJSON)
      return
    }

    // Normal predict workflow
    onGeometryDrawnPredict(geometry)
  }


  // ========================================
  // LIFECYCLE
  // ========================================
  onMounted(() => {
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', stopDrag)
    document.addEventListener('click', onClickOutside)
    fetchUhiRange()
    fetchTBase()
  })

  onBeforeUnmount(() => {
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', stopDrag)
    document.removeEventListener('click', onClickOutside)
  })
</script>

<style src="./App.css"></style>


