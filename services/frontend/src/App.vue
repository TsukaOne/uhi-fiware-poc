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
    <div v-if="showToolbox" class="toolbox-bar">
      <button class="tool-btn" title="Metadata">
        <i class="fas fa-circle-info"></i>
      </button>

      <button class="tool-btn" title="Draw Polygon">
        <i class="fas fa-draw-polygon"></i>
      </button>

      <button class="tool-btn" title="Draw Bounding Box">
        <i class="fas fa-vector-square"></i>
      </button>

      <button class="tool-btn" title="Download Data">
        <i class="fas fa-download"></i>
      </button>

      <button class="tool-btn" title="Swipe Content">
        <i class="fas fa-arrows-left-right"></i>
      </button>
    </div>

    <!-- 3D VIEWER -->
    <CesiumViewer 
      ref="viewer"
      :layers="layers"
      :activeLayers="activeLayers"
      :viewMode="viewMode"
      :buildingVisible="buildingVisible"
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

const {
  viewMode,
  showLayers,
  layers,
  activeLayers,
  buildingVisible,
  showToolbox,
  set2D,
  set3D,
  toggleLayersPanel,
  toggleLayer,
  setOpacity,
  toggleBuildings,
  toggleToolbox
} = useAppState()
</script>

<style src="./App.css"></style>


