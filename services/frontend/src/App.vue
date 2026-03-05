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

      <button class="tool-btn" title="Metadata">
        <i class="fas fa-circle-info"></i>
      </button>

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

      <button class="tool-btn" title="Download Data">
        <i class="fas fa-download"></i>
      </button>

      <button class="tool-btn" :class="{ active: swipeEnabled }" title="Swipe Content" @click="handleSwipeClick">
        <i class="fas fa-arrows-left-right"></i>
      </button>

      <div class="sun-sim-container">
        <button
          class="tool-btn"
          title="Sun Simulation"
          @click="showSunSimPanel = !showSunSimPanel"
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
            <label class="sun-sim-toggle">
              <input
                type="checkbox"
                :checked="sunSimEnabled"
                @change="toggleSunSim"
              />
              <span class="toggle-slider"></span>
            </label>
          </div>

          <div class="sun-sim-body" :class="{ disabled: !sunSimEnabled }">
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
                :disabled="!sunSimEnabled"
                class="sun-sim-slider"
              />
              <span class="slider-label">24:00</span>
            </div>

            <div class="sun-sim-presets">
              <button @click="setSunSimTime(360)" :disabled="!sunSimEnabled">06:00</button>
              <button @click="setSunSimTime(540)" :disabled="!sunSimEnabled">09:00</button>
              <button @click="setSunSimTime(720)" :disabled="!sunSimEnabled">12:00</button>
              <button @click="setSunSimTime(900)" :disabled="!sunSimEnabled">15:00</button>
              <button @click="setSunSimTime(1080)" :disabled="!sunSimEnabled">18:00</button>
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
          <span>Zone Preview</span>
          <i class="fas fa-check-circle" v-if="workflowStep >= 2"></i>
        </div>
        <div class="wf-arrow">→</div>
        <div class="workflow-step" :class="{ active: workflowStep === 2 }">
          <div class="wf-num">3</div>
          <span>Configure & Predict</span>
        </div>

        <div class="wf-actions">
          <button class="wf-btn secondary" @click="cancelWorkflow">
            <i class="fas fa-times"></i> Cancel
          </button>
          <button
            v-if="workflowStep === 1"
            class="wf-btn primary"
            @click="confirmPreviewAndOpenPanel"
          >
            Configure Parameters <i class="fas fa-arrow-right"></i>
          </button>
          <button
            v-if="workflowStep === 2"
            class="wf-btn secondary"
            @click="backToPreview"
          >
            <i class="fas fa-arrow-left"></i> Back
          </button>
        </div>
      </div>
    </Transition>

    <!-- ======================================== -->
    <!-- STEP 3 : PREDICTION PANEL (slide-in)    -->
    <!-- ======================================== -->
    <PredictionPanel
      :visible="showPredictionPanel"
      :geometry="activeGeometry"
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
      @geometry-drawn="onGeometryDrawn"
      @drawing-active="onDrawingActive"
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
      @toggle-layer="toggleLayer"
      @set-opacity="setOpacity"
      @toggle-buildings="toggleBuildings"
      @toggle-trees="toggleTrees"
      @set-swipe-left="onSetSwipeLeft"
      @set-swipe-right="onSetSwipeRight"
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
  const showPredictionPanel = ref(false)  // Params panel
  const workflowStep = ref(0)             // 0=none, 1=preview, 2=params


  function onGeometryDrawn(geometry) {
    addGeometry(geometry)
    stopDrawing()
    activeGeometry.value = geometry
    showSelectionOverlay.value = true
    showWorkflowBar.value = true
    workflowStep.value = 1
  }

  // User confirmed preview → open prediction panel
  function confirmPreviewAndOpenPanel() {
    workflowStep.value = 2
    showPredictionPanel.value = true
  }

  // Back from panel to preview step
  function backToPreview() {
    workflowStep.value = 1
    showPredictionPanel.value = false
  }
  // Close prediction panel
  function closePredictionPanel() {
    showPredictionPanel.value = false
    workflowStep.value = 1
  }
  // Cancel entire workflow
  function cancelWorkflow() {
    showSelectionOverlay.value = false
    showWorkflowBar.value = false
    showPredictionPanel.value = false
    workflowStep.value = 0
    activeGeometry.value = null
  }

  // Called when prediction panel emits 'predict'
  function onPredict(payload) {
    console.log('→ Prediction launched:', payload)
    // TODO: call your API here
  }

  // ========================================
  // LIFECYCLE
  // ========================================
  onMounted(() => {
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', stopDrag)
    document.addEventListener('click', onClickOutside)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', stopDrag)
    document.removeEventListener('click', onClickOutside)
  })
</script>

<style src="./App.css"></style>


