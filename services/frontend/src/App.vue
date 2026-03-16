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

      <!-- METADATA BUTTON WITH DROPDOWN -->
      <div class="predict-container">
        <button
          class="tool-btn"
          title="Zone Metadata"
          @click="toggleMetadataMenu"
          :class="{ active: showMetadataMenu || metadataMode }"
        >
          <i class="fas fa-circle-info"></i>
        </button>

        <div v-if="showMetadataMenu" class="predict-menu">
          <button class="predict-menu-item" @click="startMetadataPolygon">
            <i class="fas fa-draw-polygon"></i>
            Draw Polygon
          </button>
          <button class="predict-menu-item" @click="startMetadataBBox">
            <i class="fas fa-vector-square"></i>
            Draw Bounding Box
          </button>
        </div>
      </div>

      <!-- PREDICT BUTTON WITH DROPDOWN MENU -->
      <div class="predict-container">
        <button
          class="tool-btn"
          title="Predict with drawing tools"
          @click="togglePredictMenu"
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

      <!-- DOWNLOAD BUTTON WITH DROPDOWN -->
      <div class="predict-container">
        <button
          class="tool-btn"
          title="Download Data"
          @click="toggleDownloadMenu"
          :class="{ active: showDownloadMenu }"
        >
          <i class="fas fa-download"></i>
        </button>

        <div v-if="showDownloadMenu" class="predict-menu download-menu">
          <button class="predict-menu-item" @click="downloadFullMap">
            <i class="fas fa-globe"></i>
            Full Map (UHI)
          </button>
          <button class="predict-menu-item" @click="startDownloadZonePolygon">
            <i class="fas fa-draw-polygon"></i>
            Crop Polygon
          </button>
          <button class="predict-menu-item" @click="startDownloadZoneBBox">
            <i class="fas fa-vector-square"></i>
            Crop Bounding Box
          </button>
        </div>
      </div>

      <button class="tool-btn" :class="{ active: swipeEnabled }" title="Swipe Content" @click="handleSwipeClick">
        <i class="fas fa-arrows-left-right"></i>
      </button>

      <button
        class="tool-btn"
        :class="{ active: showTBaseSlider }"
        title="Temperature Reference (VLINDER)"
        @click="showTBaseSlider = !showTBaseSlider"
      >
        <i class="fas fa-thermometer-half"></i>
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
    <div v-if="isDrawingActive" class="drawing-hint">
      <i class="fas fa-info-circle"></i>
      <span>Left click to add points · Right click to confirm</span>
    </div>

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
        <div class="workflow-step" :class="{ done: workflowStep >= 1 }">
          <div class="wf-num">1</div>
          <span>Zone Selected</span>
          <i class="fas fa-check-circle" v-if="workflowStep >= 1"></i>
        </div>
        <div class="wf-arrow">→</div>
        <div class="workflow-step" :class="{ active: workflowStep === 1, done: workflowStep >= 2 }">
          <div class="wf-num">2</div>
          <span>Place Objects</span>
          <i class="fas fa-check-circle" v-if="workflowStep >= 2"></i>
        </div>
        <div class="wf-arrow">→</div>
        <div class="workflow-step" :class="{ active: workflowStep === 2, done: workflowStep >= 3 }">
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
            Predict <i class="fas fa-arrow-right"></i>
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
    <!-- ZONE OBJECTS PANEL (drag & drop 3D)     -->
    <!-- ======================================== -->
    <ZoneObjectsPanel
      :visible="showZoneObjectsPanel"
      :geometry="activeGeometry"
      :cesiumViewer="cesiumViewerInstance"
      @close="showZoneObjectsPanel = false"
      @objects-changed="onZoneObjectsChanged"
    />

    <!-- ======================================== -->
    <!-- ZONE INFO PANEL (right side, zone data) -->
    <!-- ======================================== -->
    <ZoneInfoPanel
      :visible="showZoneInfoPanel"
      :geometry="activeGeometry"
      @close="showZoneInfoPanel = false"
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
      @toggle-layer="toggleLayer"
      @set-opacity="setOpacity"
      @toggle-buildings="toggleBuildings"
      @toggle-trees="toggleTrees"
      @set-swipe-left="onSetSwipeLeft"
      @set-swipe-right="onSetSwipeRight"
    />

    <!-- T_BASE SLIDER -->
    <TBaseSlider
      v-if="showTBaseSlider"
      v-model="tBase"
    />
  </div>
</template>

<script setup>
  import { useAppState } from './App.js'
  import CesiumViewer from './components/CesiumViewer.vue'
  import LayerControls from './components/LayerControls.vue'
  import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
  import SelectionOverlay from './components/SelectionOverlay.vue'
  import PredictionPanel from './components/PredictionPanel.vue'
  import ZoneObjectsPanel from './components/ZoneObjectsPanel.vue'
  import ZoneInfoPanel from './components/ZoneInfoPanel.vue'
  import PixelInfoPanel from './components/PixelInfoPanel.vue'
  import TBaseSlider from './components/TBaseSlider.vue'
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
  const showTBaseSlider = ref(false)
  const tBase = ref(15.0)
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
    if (isSwipeDragging.value) {
      swipePosition.value = Math.max(0.05, Math.min(0.95, e.clientX / window.innerWidth))
    }
  }

  function onClickOutside(e) {
    const toolbox = document.querySelector('.toolbox-bar')
    if (toolbox && !toolbox.contains(e.target)) {
      showPredictMenu.value = false
      showSunSimPanel.value = false
      showMetadataMenu.value = false
      showDownloadMenu.value = false
    }
  }

  function stopDrag() {
    isDraggingToolbox.value = false
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

  function handleSwipeClick() {
    toggleSwipe()
    if (swipeEnabled.value && !showLayers.value) {
      showLayers.value = true
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
    if (isWorkflowActive.value || metadataMode.value || downloadMode.value) return

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
  // METADATA MODE (draw zone → show stats)
  // ========================================
  const showMetadataMenu = ref(false)
  const metadataMode = ref(false)

  function toggleMetadataMenu() {
    showMetadataMenu.value = !showMetadataMenu.value
    showPredictMenu.value = false
    showDownloadMenu.value = false
  }

  function startMetadataPolygon() {
    metadataMode.value = true
    showMetadataMenu.value = false
    startDrawingPolygon()
  }

  function startMetadataBBox() {
    metadataMode.value = true
    showMetadataMenu.value = false
    startDrawingBoundingBox()
  }

  // ========================================
  // DOWNLOAD MODE (full or crop)
  // ========================================
  const showDownloadMenu = ref(false)
  const downloadMode = ref(false)

  function toggleDownloadMenu() {
    showDownloadMenu.value = !showDownloadMenu.value
    showPredictMenu.value = false
    showMetadataMenu.value = false
  }

  async function downloadFullMap() {
    showDownloadMenu.value = false
    try {
      const resp = await fetch(`${PREDICTION_URL}/predict/download`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ layer: 'uhi', geometry: null }),
      })
      if (!resp.ok) throw new Error(`Download failed: ${resp.status}`)
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'uhi_full.tif'
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Download failed:', err)
      alert('Download failed: ' + err.message)
    }
  }

  function startDownloadZonePolygon() {
    downloadMode.value = true
    showDownloadMenu.value = false
    startDrawingPolygon()
  }

  function startDownloadZoneBBox() {
    downloadMode.value = true
    showDownloadMenu.value = false
    startDrawingBoundingBox()
  }

  // ========================================
  // GEOMETRY DRAWN HANDLER (routes to correct mode)
  // ========================================
  function onGeometryDrawnRouter(geometry) {
    if (metadataMode.value) {
      // Metadata mode: show zone info panel with stats
      addGeometry(geometry)
      stopDrawing()
      metadataMode.value = false
      activeGeometry.value = geometry
      showZoneInfoPanel.value = true
      showSelectionOverlay.value = true
      showWorkflowBar.value = true
      workflowStep.value = 1
      // Don't open objects panel in metadata mode
      showZoneObjectsPanel.value = false
      showPredictionPanel.value = false
      return
    }

    if (downloadMode.value) {
      // Download mode: crop and download
      addGeometry(geometry)
      stopDrawing()
      downloadMode.value = false
      downloadCroppedMap(geometry)
      return
    }

    // Normal predict workflow
    onGeometryDrawnPredict(geometry)
  }

  async function downloadCroppedMap(geometry) {
    if (!geometry?.geoJSON) return
    try {
      const resp = await fetch(`${PREDICTION_URL}/predict/download`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ layer: 'uhi', geometry: geometry.geoJSON }),
      })
      if (!resp.ok) throw new Error(`Download failed: ${resp.status}`)
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'uhi_crop.tif'
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Download failed:', err)
      alert('Download failed: ' + err.message)
    }
  }

  // ========================================
  // LIFECYCLE
  // ========================================
  onMounted(() => {
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', stopDrag)
    document.addEventListener('click', onClickOutside)
    fetchUhiRange()
  })

  onBeforeUnmount(() => {
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', stopDrag)
    document.removeEventListener('click', onClickOutside)
  })
</script>

<style src="./App.css"></style>


