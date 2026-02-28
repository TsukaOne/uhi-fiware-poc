<template>
  <div class="layer-panel" :class="{ collapsed: isCollapsed }">
    <button class="toggle-btn" @click="isCollapsed = !isCollapsed">
      <i v-if="isCollapsed" class="fas fa-chevron-left"></i>
      <i v-else class="fas fa-chevron-right"></i>
      Layers
    </button>
    
    <div class="panel-content" v-show="!isCollapsed">
      <!-- SECTION A: URBAN HEAT ISLANDS -->
      <div class="layer-section">
        <h3 class="section-title">
          <i class="fas fa-temperature-high"></i>
          Urban Heat Islands
        </h3>
        <div class="layer-list">
          <div 
            v-for="layer in getLayersByCategory('uhi_maps')" 
            :key="layer.id"
            class="layer-item"
            :class="{ active: layer.visible }"
          >
            <div class="layer-header">
              <label class="checkbox-wrapper">
                <input 
                  type="checkbox" 
                  :checked="layer.visible"
                  @change="$emit('toggle-layer', layer.id)"
                />
                <span class="checkmark"></span>
                <span class="layer-name">{{ layer.name }}</span>
              </label>
            </div>
            
            <p class="layer-description">{{ layer.description }}</p>
            
            <div class="opacity-control" v-if="layer.visible">
              <label>Opacity: {{ Math.round(layer.opacity * 100) }}%</label>
              <input 
                type="range" 
                min="0" 
                max="1" 
                step="0.1"
                :value="layer.opacity"
                @input="$emit('set-opacity', layer.id, parseFloat($event.target.value))"
              />
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

      <!-- SECTION B: ADDITIONAL MAP LAYERS -->
      <div class="layer-section">
        <h3 class="section-title">
          <i class="fas fa-layer-group"></i>
          Map Layers
        </h3>
        <div class="layer-list">
          <div 
            v-for="layer in getLayersByCategory('map_layers')" 
            :key="layer.id"
            class="layer-item"
            :class="{ active: layer.visible }"
          >
            <div class="layer-header">
              <label class="checkbox-wrapper">
                <input 
                  type="checkbox" 
                  :checked="layer.visible"
                  @change="$emit('toggle-layer', layer.id)"
                />
                <span class="checkmark"></span>
                <span class="layer-name">{{ layer.name }}</span>
              </label>
            </div>
            
            <p class="layer-description">{{ layer.description }}</p>
            
            <div class="opacity-control" v-if="layer.visible">
              <label>Opacity: {{ Math.round(layer.opacity * 100) }}%</label>
              <input 
                type="range" 
                min="0" 
                max="1" 
                step="0.1"
                :value="layer.opacity"
                @input="$emit('set-opacity', layer.id, parseFloat($event.target.value))"
              />
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

      <!-- SECTION C: 3D TILESET -->
      <div class="layer-section">
        <h3 class="section-title">
          <i class="fas fa-cube"></i>
          3D Tileset
        </h3>
        <div class="layer-list">
          <div class="layer-item" :class="{ active: buildingVisible }">
            <div class="layer-header">
              <label class="checkbox-wrapper">
                <input 
                  type="checkbox" 
                  :checked="buildingVisible"
                  @change="$emit('toggle-buildings')"
                />
                <span class="checkmark"></span>
                <span class="layer-name">Buildings 3D</span>
              </label>
            </div>
            <p class="layer-description">Interactive 3D building models snapped to terrain</p>
          </div>
        </div>
      </div>

      <!-- INFO SECTION -->
      <div class="info-section">
        <h4>About This Project</h4>
        <p>Urban Heat Island monitoring system for Brussels using FIWARE and satellite imagery.</p>
        <ul>
          <li><strong>NDVI:</strong> Vegetation density</li>
          <li><strong>NDWI:</strong> Water presence</li>
          <li><strong>UHI:</strong> Heat risk prediction</li>
          <li><strong>DTM:</strong> Digital Terrain Model</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useLayerControls } from './LayerControls.js'

const props = defineProps({
  layers: {
    type: Array,
    required: true
  },
  activeLayers: {
    type: Array,
    default: () => []
  },
  buildingVisible: {
    type: Boolean,
    default: true
  }
})

defineEmits(['toggle-layer', 'set-opacity', 'toggle-buildings'])


const { isCollapsed, getLegendStyle } = useLayerControls()

function getLayersByCategory(category) {
  return props.layers.filter(layer => layer.category === category)
}
</script>
<style src="./LayerControls.css"></style>
