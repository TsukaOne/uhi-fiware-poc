<template>
  <div class="app-container">
    <!-- WELCOME SPLASH -->
    <Transition name="welcome-fade">
      <div v-if="showWelcome" class="welcome-overlay" @click.self="enterApp">
        <div class="welcome-card">
          <div class="welcome-eyebrow">By FARI with the support of VBX</div>
          <h1 class="welcome-title">Urban Heat Islands Viewer</h1>
          <p class="welcome-subtitle">
            By <strong>FARI &mdash; AI for the Common Good</strong>
            with the support of the <strong>City of Brussels</strong>.
          </p>

          <div class="welcome-logos">
            <img :src="fariLogo" alt="FARI - AI for the Common Good" class="welcome-logo welcome-logo-fari" />
            <span class="welcome-logo-sep">&times;</span>
            <img :src="vbxLogo" alt="Ville de Bruxelles" class="welcome-logo welcome-logo-vbx" />
          </div>

          <button class="welcome-enter-btn" @click="enterApp">
            <i class="fas fa-arrow-right"></i>
            Enter the viewer
          </button>
        </div>
      </div>
    </Transition>

    <!-- COLLAB CORNER BADGE (persistent, bottom-right) -->
    <div class="collab-corner" title="A FARI × Ville de Bruxelles collaboration">
      <div class="collab-corner-logos">
        <img :src="fariLogo" alt="FARI" class="collab-corner-logo collab-corner-logo-fari" />
        <span class="collab-corner-logo-sep">with the support of </span>
        <img :src="vbxLogo" alt="Ville de Bruxelles" class="collab-corner-logo collab-corner-logo-vbx" />
      </div>
    </div>

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

    <!--SELECTION OVERLAY --> 
    <SelectionOverlay
      :visible="showSelectionOverlay"
      :geometry="activeGeometry"
      :cesiumViewer="cesiumViewerInstance"
      :viewMode="viewMode"
    />

   
    <!-- WORKFLOW BOTTOM BAR        -->
    <!-- Appears after drawing, before prediction -->
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

   
    <!-- TOOL MODAL (Metadata / Download)        -->
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
              <span class="layer-info-card-label" title="Average value across all valid pixels in the area">Mean <i class="fas fa-question-circle" style="font-size:9px;color:rgba(255,255,255,0.25);margin-left:2px;"></i></span>
              <span class="layer-info-card-value">{{ layerInfoStats.mean }}</span>
            </div>
            <div class="layer-info-card">
              <span class="layer-info-card-label" title="Lowest pixel value found in the area">Min <i class="fas fa-question-circle" style="font-size:9px;color:rgba(255,255,255,0.25);margin-left:2px;"></i></span>
              <span class="layer-info-card-value min">{{ layerInfoStats.min }}</span>
            </div>
            <div class="layer-info-card">
              <span class="layer-info-card-label" title="Highest pixel value found in the area">Max <i class="fas fa-question-circle" style="font-size:9px;color:rgba(255,255,255,0.25);margin-left:2px;"></i></span>
              <span class="layer-info-card-value max">{{ layerInfoStats.max }}</span>
            </div>
            <div class="layer-info-card">
              <span class="layer-info-card-label" title="Standard deviation — measures how spread out the values are from the mean">Std Dev <i class="fas fa-question-circle" style="font-size:9px;color:rgba(255,255,255,0.25);margin-left:2px;"></i></span>
              <span class="layer-info-card-value std">{{ layerInfoStats.std }}</span>
            </div>
            <div class="layer-info-card wide">
              <span class="layer-info-card-label" title="Total number of valid pixels analyzed">Pixels <i class="fas fa-question-circle" style="font-size:9px;color:rgba(255,255,255,0.25);margin-left:2px;"></i></span>
              <span class="layer-info-card-value">{{ layerInfoStats.pixel_count?.toLocaleString() }}</span>
            </div>
          </div>
        </div>
      </div>
    </Transition>

   
    <!-- DOWNLOAD CONFIRM DIALOG -->
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

    
    <!-- ZONE OBJECTS PANEL (drag & drop 3D)     -->
    <ZoneObjectsPanel
      :visible="showZoneObjectsPanel"
      :geometry="activeGeometry"
      :cesiumViewer="cesiumViewerInstance"
      @objects-changed="onZoneObjectsChanged"
    />

    
    <!-- ZONE INFO PANEL (right side, zone data) -->
    <ZoneInfoPanel
      :visible="showZoneInfoPanel"
      :geometry="activeGeometry"
      ref="zoneInfoPanelRef"
      @stats-loaded="onZoneStatsLoaded"
    />

    <!-- PREDICTION PANEL (replaces info panel)  -->
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
      :uhiMin="uhiMin"
      :uhiMax="uhiMax"
      :predictionOverlay="predictionOverlay"
      :sensorData="visibleSensors"
      :sensorsVisible="anySensorsVisible"
      @geometry-drawn="onGeometryDrawnRouter"
      @drawing-active="onDrawingActive"
      @sensor-click="onSensorClick"
    />

    <!-- SENSOR INFO POPUP (click on sensor dot) -->
    <Transition name="pixel-fade">
      <div v-if="selectedSensor" class="sensor-popup" :style="sensorPopupStyle">
        <div class="sensor-popup-header">
          <span class="sensor-popup-title">
            <i class="fas fa-satellite-dish" style="color: #4ade80;"></i>
            {{ selectedSensor.station_name || selectedSensor.station_id }}
          </span>
          <button class="sensor-popup-close" @click="selectedSensor = null">
            <i class="fas fa-times"></i>
          </button>
        </div>
        <div class="sensor-popup-body">
          <div class="sensor-popup-row" v-if="selectedSensor.temperature != null">
            <i class="fas fa-thermometer-half" style="color: #f87171;"></i>
            <span class="sensor-popup-label">Temperature</span>
            <span class="sensor-popup-val">{{ selectedSensor.temperature.toFixed(1) }}°C</span>
          </div>
          <div class="sensor-popup-row" v-if="selectedSensor.humidity != null">
            <i class="fas fa-droplet" style="color: #38bdf8;"></i>
            <span class="sensor-popup-label">Humidity</span>
            <span class="sensor-popup-val">{{ selectedSensor.humidity.toFixed(0) }}%</span>
          </div>
          <div class="sensor-popup-row" v-if="selectedSensor.pressure != null">
            <i class="fas fa-gauge" style="color: #a78bfa;"></i>
            <span class="sensor-popup-label">Pressure</span>
            <span class="sensor-popup-val">{{ selectedSensor.pressure.toFixed(1) }} hPa</span>
          </div>
          <div class="sensor-popup-row" v-if="selectedSensor.wind_speed != null">
            <i class="fas fa-wind" style="color: #94a3b8;"></i>
            <span class="sensor-popup-label">Wind</span>
            <span class="sensor-popup-val">{{ selectedSensor.wind_speed.toFixed(1) }} m/s</span>
          </div>
          <div class="sensor-popup-row" v-if="selectedSensor.wind_direction != null">
            <i class="fas fa-compass" style="color: #94a3b8;"></i>
            <span class="sensor-popup-label">Direction</span>
            <span class="sensor-popup-val">{{ selectedSensor.wind_direction.toFixed(0) }}°</span>
          </div>
          <div class="sensor-popup-divider"></div>
          <div class="sensor-popup-row meta">
            <i class="fas fa-tag" style="color: #6b7280;"></i>
            <span class="sensor-popup-label">Provider</span>
            <span class="sensor-popup-val">{{ selectedSensor.provider }}</span>
          </div>
          <div class="sensor-popup-row meta">
            <i class="fas fa-fingerprint" style="color: #6b7280;"></i>
            <span class="sensor-popup-label">Station ID</span>
            <span class="sensor-popup-val mono">{{ selectedSensor.station_id.slice(0, 12) }}…</span>
          </div>
          <div class="sensor-popup-row meta" v-if="selectedSensor.observed_at">
            <i class="fas fa-clock" style="color: #6b7280;"></i>
            <span class="sensor-popup-label">Observed</span>
            <span class="sensor-popup-val">{{ formatSensorTime(selectedSensor.observed_at) }}</span>
          </div>
          <div class="sensor-popup-row meta" v-if="selectedSensor.latitude != null">
            <i class="fas fa-map-pin" style="color: #6b7280;"></i>
            <span class="sensor-popup-label">Location</span>
            <span class="sensor-popup-val">{{ selectedSensor.latitude.toFixed(4) }}°, {{ selectedSensor.longitude.toFixed(4) }}°</span>
          </div>
        </div>
      </div>
    </Transition>

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
      :uhiMin="uhiMin"
      :uhiMax="uhiMax"
      :predictionHistory="predictionHistory"
      :vlinderSensors="vlinderSensors"
      :scSensors="scSensors"
      :vlinderVisible="vlinderVisible"
      :scVisible="scVisible"
      @toggle-layer="toggleLayer"
      @set-opacity="setOpacity"
      @toggle-buildings="toggleBuildings"
      @toggle-trees="toggleTrees"
      @set-swipe-left="onSetSwipeLeft"
      @set-swipe-right="onSetSwipeRight"
      @layer-metadata="onLayerMetadata"
      @layer-download="onLayerDownload"
      @toggle-prediction-history="togglePredictionHistory"
      @toggle-vlinder="toggleVlinder"
      @toggle-sensors-community="toggleSensorsCommunity"
      @refresh-sensors="fetchSensors"
      @select-sensor="onSelectSensor"
    />

  </div>
</template>

<script setup>
    import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
    import * as Cesium from 'cesium'

    // Components
    import CesiumViewer     from './components/CesiumViewer/CesiumViewer.vue'
    import LayerControls    from './components/LayerControls/LayerControls.vue'
    import SelectionOverlay from './components/SelectionOverlay/SelectionOverlay.vue'
    import PredictionPanel  from './components/PredictionPanel/PredictionPanel.vue'
    import ZoneObjectsPanel from './components/ZoneObjectsPanel/ZoneObjectsPanel.vue'
    import ZoneInfoPanel    from './components/ZoneInfoPanel/ZoneInfoPanel.vue'
    // Assets
    import fariLogo from './images/logos/fari_logos.png'
    import vbxLogo  from './images/logos/vbx_logos.png'

    // Composables
    import { useAppState }   from './App.js'
    import { orionApi }      from './services/orionApi.js'
    import { useDraggable }  from './composables/App/useDraggable.js'
    import { useWorkflow }   from './composables/App/useWorkflow.js'
    import { useLayerInfo }  from './composables/App/useLayerInfo.js'
    import { useDownload }   from './composables/App/useDownload.js'


  // ── Global app state (view mode, layers, drawing, swipe, sun sim) ──────────
  const {
    viewMode, showLayers, layers, activeLayers, buildingVisible, treeVisible,
    showToolbox, drawingMode, showPredictMenu, drawnGeometries,
    set2D, set3D, toggleLayersPanel, toggleLayer, setOpacity,
    toggleBuildings, toggleTrees, toggleToolbox, togglePredictMenu,
    startDrawingPolygon, startDrawingBoundingBox, stopDrawing, addGeometry,
    swipeEnabled, swipeLeftLayerId, swipeRightLayerId, swipePosition, toggleSwipe,
    sunSimEnabled, sunSimTime, toggleSunSim, setSunSimTime
  } = useAppState()


  // ── Welcome splash ──────────────────────────────────────────────────────────
  const showWelcome = ref(true)
  function enterApp() { showWelcome.value = false }


  // ── Cesium viewer ref ───────────────────────────────────────────────────────
  const cesiumViewerRef = ref(null)
  const layerControlsRef = ref(null)
  const zoneInfoPanelRef = ref(null)
  const cesiumViewerInstance = computed(() =>
    cesiumViewerRef.value?.getViewer?.() ?? null
  )


  // ── Draggable floating panels ───────────────────────────────────────────────
  // useDraggable returns: { style, startDrag, onMouseMove, stopDrag }
  // Destructuring with aliases preserves the existing template variable names.
  const {
    style: toolboxStyle,
    startDrag: startDragToolbox,
    onMouseMove: onToolboxMouseMove,
    stopDrag: stopToolboxDrag,
  } = useDraggable(window.innerWidth / 2 - 200, 90)

  // ── Prediction workflow state machine ───────────────────────────────────────
  const {
    activeGeometry, showSelectionOverlay, showWorkflowBar, showPredictionPanel,
    workflowStep, showZoneObjectsPanel, showZoneInfoPanel, zoneObjects,
    predictionOverlay, zoneStatsData, predictionHistory,
    onGeometryDrawnPredict, goToStep, goToPredict, backToObjects,
    closePredictionPanel, cancelWorkflow, onZoneObjectsChanged, onPredict,
    togglePredictionHistory,
  } = useWorkflow({
    addGeometry,
    stopDrawing,
    set3D,
    getViewMode: () => viewMode.value,
  })


  // ── Zone stats forwarding (ZoneInfoPanel → PredictionPanel) ────────────────
  function onZoneStatsLoaded(stats) {
    zoneStatsData.value = stats
  }

  // ── Drawing state ───────────────────────────────────────────────────────────
  const isDrawingActive = ref(false)
  function onDrawingActive(active) { isDrawingActive.value = active }

  // Lock 3D interaction while the user is drawing or in the workflow
  const isWorkflowActive = computed(
    () => isDrawingActive.value || showWorkflowBar.value
  )

  // Drawing always starts in 2D for a clear top-down view
  watch(drawingMode, (mode) => {
    if (mode && viewMode.value !== '2D') set2D()
  })


  // ── Sensor click popup ──────────────────────────────────────────────────────
  const selectedSensor = ref(null)
  const sensorPopupX = ref(0)
  const sensorPopupY = ref(0)

  const sensorPopupStyle = computed(() => {
    const x = Math.min(sensorPopupX.value + 16, window.innerWidth - 300)
    const y = Math.min(sensorPopupY.value - 20, window.innerHeight - 400)
    return { left: Math.max(8, x) + 'px', top: Math.max(70, y) + 'px' }
  })

  function onSensorClick({ sensor, screenX, screenY }) {
    selectedSensor.value = sensor
    sensorPopupX.value = screenX
    sensorPopupY.value = screenY
  }

  /**
   * Called when a sensor is clicked in the LayerControls panel.
   * Flies the camera to the sensor location and opens its popup.
   */
  function onSelectSensor(sensor) {
    if (sensor.latitude == null || sensor.longitude == null) return

    const viewer = cesiumViewerInstance.value
    if (!viewer) return

    // Fly to the sensor (works in both 2D top-down and 3D modes)
    const height = viewMode.value === '2D' ? 800 : 1200
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(sensor.longitude, sensor.latitude, height),
      duration: 1.5,
      complete: () => {
        // After the camera arrives, convert the sensor's world position to screen coords
        // and show the popup at that position
        const worldPos = Cesium.Cartesian3.fromDegrees(sensor.longitude, sensor.latitude, 20)
        const screenPos = Cesium.SceneTransforms.worldToWindowCoordinates(viewer.scene, worldPos)
        if (screenPos) {
          onSensorClick({ sensor, screenX: screenPos.x, screenY: screenPos.y })
        } else {
          // Fallback: center of screen
          onSensorClick({ sensor, screenX: window.innerWidth / 2, screenY: window.innerHeight / 2 })
        }
      }
    })
  }

  function formatSensorTime(isoStr) {
    if (!isoStr) return '—'
    try {
      return new Date(isoStr).toLocaleString()
    } catch { return isoStr }
  }


  // ── Layer statistics modal ──────────────────────────────────────────────────
  const {
    showLayerInfoChoice, showLayerInfoResults, layerInfoLoading, layerInfoError,
    layerInfoStats, layerInfoName, layerInfoRegionLabel, infoMode,
    onLayerMetadata, onInfoChoice, onInfoGeometryDrawn, closeLayerInfoResults,
  } = useLayerInfo({
    getLayers:              () => layers,
    startDrawingBoundingBox,
    startDrawingPolygon,
    addGeometry,
    stopDrawing,
  })


  // ── Download flow ───────────────────────────────────────────────────────────
  const {
    showToolModal, toolModalType, toolModalLayerId, toolModalLayerName,
    showDownloadConfirm, downloadConfirmText, isDownloading, downloadMode,
    onLayerDownload, closeToolModal, onToolModalChoice,
    onDownloadGeometryDrawn, executeDownload,
  } = useDownload({
    getLayers:              () => layers,
    startDrawingBoundingBox,
    addGeometry,
    stopDrawing,
  })


  // ── Multi-sensor data ──────────────────────────────────────────────────────
  const allSensors = ref([])
  const vlinderVisible = ref(false)
  const scVisible = ref(false)

  const vlinderSensors = computed(() => allSensors.value.filter(s => s.provider === 'vlinder'))
  const scSensors = computed(() => allSensors.value.filter(s => s.provider === 'sensors_community'))

  // Sensors visible on the map = union of enabled providers
  const visibleSensors = computed(() => {
    const out = []
    if (vlinderVisible.value) out.push(...vlinderSensors.value)
    if (scVisible.value) out.push(...scSensors.value)
    return out
  })
  const anySensorsVisible = computed(() => vlinderVisible.value || scVisible.value)

  async function fetchSensors() {
    try {
      allSensors.value = await orionApi.getTemperatureSensors()
    } catch (err) {
      console.warn('Sensor fetch from Orion failed:', err)
    }
  }

  function toggleVlinder() {
    vlinderVisible.value = !vlinderVisible.value
    if (vlinderVisible.value && allSensors.value.length === 0) fetchSensors()
  }

  function toggleSensorsCommunity() {
    scVisible.value = !scVisible.value
    if (scVisible.value && allSensors.value.length === 0) fetchSensors()
  }


  // ── UHI range data ─────────────────────────────────────────────────────────
  const uhiMin = ref(null)
  const uhiMax = ref(null)

  async function fetchUhiRange() {
    try {
      const entity = await orionApi.getUhiEntity()
      const range = entity?.valueRange?.value
      if (range) {
        uhiMin.value = range.min
        uhiMax.value = range.max
      }
    } catch (err) {
      console.warn('Failed to fetch UHI range from Orion:', err)
    }
  }

  // ── Toolbox: swipe, sun sim, mutual exclusion ───────────────────────────────
  const showSunSimPanel  = ref(false)
  const isSwipeDragging  = ref(false)

  const sunSimTimeFormatted = computed(() => {
    const hours = Math.floor(sunSimTime.value / 60)
    const mins  = sunSimTime.value % 60
    return `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`
  })

  // Sun simulation requires 3D
  watch(sunSimEnabled, (enabled) => {
    if (enabled && viewMode.value !== '3D') set3D()
  })

  /** Ensure only one toolbox tool is active at a time */
  function deactivateToolsExcept(keepTool) {
    if (keepTool !== 'swipe'  && swipeEnabled.value)   toggleSwipe()
    if (keepTool !== 'sunSim' && sunSimEnabled.value) {
      toggleSunSim()
      showSunSimPanel.value = false
    }
    if (keepTool !== 'predict') showPredictMenu.value = false
  }

  function handlePredictClick() {
    if (!showPredictMenu.value) deactivateToolsExcept('predict')
    togglePredictMenu()
  }

  function handleSunSimClick() {
    const wasEnabled = sunSimEnabled.value
    if (!wasEnabled) deactivateToolsExcept('sunSim')
    toggleSunSim()
    showSunSimPanel.value = !wasEnabled
  }

  function handleSwipeClick() {
    const wasEnabled = swipeEnabled.value
    if (!wasEnabled) deactivateToolsExcept('swipe')
    toggleSwipe()
    if (swipeEnabled.value) {
      if (!showLayers.value) showLayers.value = true
      nextTick(() => layerControlsRef.value?.openLayerSections())
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


  // ── Geometry drawn router ────────────────────────────────────────────────────
  // Directs the drawn geometry to the correct handler depending on which mode is active.
  function onGeometryDrawnRouter(geometry) {
    if (downloadMode.value) {
      onDownloadGeometryDrawn(geometry)
    } else if (infoMode.value) {
      onInfoGeometryDrawn(geometry)
    } else {
      onGeometryDrawnPredict(geometry)
    }
  }


  // ── Global mouse handlers (shared across multiple draggables + swipe) ───────
  function onMouseMove(e) {
    onToolboxMouseMove(e)
    if (isSwipeDragging.value) {
      // Keep both panels visible: clamp handle between 5% and 95% of screen width
      const SWIPE_MIN = 0.05
      const SWIPE_MAX = 0.95
      swipePosition.value = Math.max(SWIPE_MIN, Math.min(SWIPE_MAX, e.clientX / window.innerWidth))
    }
  }

  function stopDrag() {
    stopToolboxDrag()
    if (isSwipeDragging.value) {
      isSwipeDragging.value = false
      document.body.style.cursor = ''
    }
  }

  function onClickOutside(e) {
    const toolbox = document.querySelector('.toolbox-bar')
    if (toolbox && !toolbox.contains(e.target)) {
      showPredictMenu.value = false
      showSunSimPanel.value = false
    }
  }


  // ── Lifecycle ───────────────────────────────────────────────────────────────
  onMounted(() => {
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', stopDrag)
    document.addEventListener('click', onClickOutside)
    fetchUhiRange()
    fetchSensors()
  })

  onBeforeUnmount(() => {
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', stopDrag)
    document.removeEventListener('click', onClickOutside)
  })
</script>

<style src="./App.css"></style>


