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
          :class="{ active: showPredictMenu }"
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

      <button class="tool-btn" title="Swipe Content">
        <i class="fas fa-arrows-left-right"></i>
      </button>

      <button class="tool-btn" title="Sun Simulation">
        <i class="fas fa-sun"></i>
      </button>
    </div>

    <!-- 3D VIEWER -->
    <CesiumViewer
      ref="viewer"
      :layers="layers"
      :activeLayers="activeLayers"
      :viewMode="viewMode"
      :buildingVisible="buildingVisible"
      :drawingMode="drawingMode"
      @geometry-drawn="onGeometryDrawn"
    />

    <!-- LAYER CONTROLS PANEL -->
    <LayerControls
      v-if="showLayers"
      :layers="layers"
      :activeLayers="activeLayers"
      :buildingVisible="buildingVisible"
      @toggle-layer="toggleLayer"
      @set-opacity="setOpacity"
      @toggle-buildings="toggleBuildings"
    />
  </div>
</template>

<script setup>
  import { useAppState } from './App.js'
  import CesiumViewer from './components/CesiumViewer.vue'
  import LayerControls from './components/LayerControls.vue'
  import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

  const {
    viewMode,
    showLayers,
    layers,
    activeLayers,
    buildingVisible,
    showToolbox,
    drawingMode,
    showPredictMenu,
    drawnGeometries,
    set2D,
    set3D,
    toggleLayersPanel,
    toggleLayer,
    setOpacity,
    toggleBuildings,
    toggleToolbox,
    togglePredictMenu,
    startDrawingPolygon,
    startDrawingBoundingBox,
    stopDrawing,
    addGeometry
  } = useAppState()

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
  }

  function onClickOutside(e) {
    // Close predict menu when clicking outside toolbox
    if (showPredictMenu.value) {
      const toolbox = document.querySelector('.toolbox-bar')
      if (toolbox && !toolbox.contains(e.target)) {
        showPredictMenu.value = false
      }
    }
  }

  function onGeometryDrawn(geometry) {
    addGeometry(geometry)
    stopDrawing()
  }

  function stopDrag() {
    isDraggingToolbox.value = false
  }

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


