<template>
  <div class="layer-panel" :style="panelStyle">
    <!-- DRAG HANDLER  -->
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

    <!--LAYER LIST CONTENT -->
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
                  <button class="layer-about-btn" :class="{ active: expandedLayerAbout[layer.id] }" @click.prevent.stop="expandedLayerAbout[layer.id] = !expandedLayerAbout[layer.id]" title="About this layer">
                    <i class="fas fa-question-circle"></i>
                  </button>
                </div>
                <p class="layer-description">{{ layer.description }}</p>
                <!-- Expandable layer info -->
                <Transition name="section-slide">
                  <div v-if="expandedLayerAbout[layer.id] && LAYER_INFO[layer.id]" class="layer-about-panel">
                    <div class="layer-about-title">{{ LAYER_INFO[layer.id].title }}</div>
                    <p class="layer-about-text">{{ LAYER_INFO[layer.id].what }}</p>
                    <div class="layer-about-section">
                      <strong><i class="fas fa-cog"></i> How it works</strong>
                      <p>{{ LAYER_INFO[layer.id].how }}</p>
                    </div>
                    <div class="layer-about-section uhi">
                      <strong><i class="fas fa-temperature-high"></i> UHI relevance</strong>
                      <p>{{ LAYER_INFO[layer.id].uhi }}</p>
                    </div>
                  </div>
                </Transition>
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
                  <div class="legend-labels" v-if="uhiMin != null && uhiMax != null && layer.id === 'uhi_prediction'">
                    <span>Low ({{ uhiMin.toFixed(1) }})</span>
                    <span>High ({{ uhiMax.toFixed(1) }})</span>
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
                :class="{ active: entry.visible }"
              >
                <div class="history-item-header">
                  <label class="checkbox-wrapper small" @click.stop>
                    <input type="checkbox" :checked="entry.visible" @change="$emit('toggle-prediction-history', entry.id)" />
                    <span class="checkmark"></span>
                  </label>
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
                  <button class="layer-about-btn" :class="{ active: expandedLayerAbout[layer.id] }" @click.prevent.stop="expandedLayerAbout[layer.id] = !expandedLayerAbout[layer.id]" title="About this layer">
                    <i class="fas fa-question-circle"></i>
                  </button>
                </div>
                <p class="layer-description">{{ layer.description }}</p>
                <!-- Expandable layer info -->
                <Transition name="section-slide">
                  <div v-if="expandedLayerAbout[layer.id] && LAYER_INFO[layer.id]" class="layer-about-panel">
                    <div class="layer-about-title">{{ LAYER_INFO[layer.id].title }}</div>
                    <p class="layer-about-text">{{ LAYER_INFO[layer.id].what }}</p>
                    <div class="layer-about-section">
                      <strong><i class="fas fa-cog"></i> How it works</strong>
                      <p>{{ LAYER_INFO[layer.id].how }}</p>
                    </div>
                    <div class="layer-about-section uhi">
                      <strong><i class="fas fa-temperature-high"></i> UHI relevance</strong>
                      <p>{{ LAYER_INFO[layer.id].uhi }}</p>
                    </div>
                  </div>
                </Transition>
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
                  <button class="layer-about-btn" :class="{ active: expandedLayerAbout['buildings'] }" @click.prevent.stop="expandedLayerAbout['buildings'] = !expandedLayerAbout['buildings']" title="About 3D Buildings">
                    <i class="fas fa-question-circle"></i>
                  </button>
                </div>
                <p class="layer-description">Interactive 3D building models snapped to terrain</p>
                <Transition name="section-slide">
                  <div v-if="expandedLayerAbout['buildings']" class="layer-about-panel">
                    <div class="layer-about-title">{{ TILESET_INFO.buildings.title }}</div>
                    <p class="layer-about-text">{{ TILESET_INFO.buildings.description }}</p>
                    <div class="layer-about-section uhi">
                      <strong><i class="fas fa-temperature-high"></i> UHI relevance</strong>
                      <p>{{ TILESET_INFO.buildings.details }}</p>
                    </div>
                  </div>
                </Transition>
              </div>
              <div class="layer-item" :class="{ active: treeVisible }">
                <div class="layer-header">
                  <label class="checkbox-wrapper">
                    <input type="checkbox" :checked="treeVisible" @change="$emit('toggle-trees')" />
                    <span class="checkmark"></span>
                    <span class="layer-name">Trees 3D</span>
                  </label>
                  <button class="layer-about-btn" :class="{ active: expandedLayerAbout['trees'] }" @click.prevent.stop="expandedLayerAbout['trees'] = !expandedLayerAbout['trees']" title="About 3D Trees">
                    <i class="fas fa-question-circle"></i>
                  </button>
                </div>
                <p class="layer-description">Interactive 3D trees snapped to terrain</p>
                <Transition name="section-slide">
                  <div v-if="expandedLayerAbout['trees']" class="layer-about-panel">
                    <div class="layer-about-title">{{ TILESET_INFO.trees.title }}</div>
                    <p class="layer-about-text">{{ TILESET_INFO.trees.description }}</p>
                    <div class="layer-about-section uhi">
                      <strong><i class="fas fa-temperature-high"></i> UHI relevance</strong>
                      <p>{{ TILESET_INFO.trees.details }}</p>
                    </div>
                  </div>
                </Transition>
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

              <!-- VLINDER Weather Stations -->
              <div class="layer-item" :class="{ active: vlinderVisible }">
                <div class="layer-header">
                  <label class="checkbox-wrapper">
                    <input type="checkbox" :checked="vlinderVisible" @change="$emit('toggle-vlinder')" />
                    <span class="checkmark"></span>
                    <span class="layer-name">VLINDER Weather Stations</span>
                  </label>
                  <button class="layer-about-btn" :class="{ active: expandedLayerAbout['vlinder'] }" @click.prevent.stop="expandedLayerAbout['vlinder'] = !expandedLayerAbout['vlinder']" title="About VLINDER">
                    <i class="fas fa-question-circle"></i>
                  </button>
                </div>
                <p class="layer-description">UGent research weather stations ({{ vlinderSensors.length }})</p>
                <Transition name="section-slide">
                  <div v-if="expandedLayerAbout['vlinder']" class="layer-about-panel">
                    <div class="layer-about-title">{{ SENSOR_INFO.vlinder.title }}</div>
                    <p class="layer-about-text">{{ SENSOR_INFO.vlinder.description }}</p>
                    <div class="layer-about-section uhi">
                      <strong><i class="fas fa-satellite-dish"></i> How it's used</strong>
                      <p>{{ SENSOR_INFO.vlinder.details }}</p>
                    </div>
                  </div>
                </Transition>
                <!-- Dropdown list of VLINDER sensors -->
                <Transition name="section-slide">
                  <div v-if="vlinderVisible && vlinderSensors.length > 0" class="sensor-station-list">
                    <div v-for="sensor in vlinderSensors" :key="sensor.station_id" class="sensor-station-item">
                      <div class="sensor-station-header">
                        <span class="sensor-station-name">{{ sensor.station_name || sensor.station_id.slice(0, 10) }}</span>
                        <span class="sensor-station-temp" :style="{ color: tempColor(sensor.temperature) }">
                          {{ sensor.temperature != null ? sensor.temperature.toFixed(1) + '°C' : '--' }}
                        </span>
                      </div>
                      <div class="sensor-station-details">
                        <span v-if="sensor.humidity != null"><i class="fas fa-droplet"></i> {{ sensor.humidity.toFixed(0) }}%</span>
                        <span v-if="sensor.wind_speed != null"><i class="fas fa-wind"></i> {{ sensor.wind_speed.toFixed(1) }} m/s</span>
                        <span v-if="sensor.pressure != null"><i class="fas fa-gauge-high"></i> {{ sensor.pressure.toFixed(0) }} hPa</span>
                      </div>
                    </div>
                  </div>
                </Transition>
              </div>

              <!-- Sensors.community -->
              <div class="layer-item" :class="{ active: scVisible }">
                <div class="layer-header">
                  <label class="checkbox-wrapper">
                    <input type="checkbox" :checked="scVisible" @change="$emit('toggle-sensors-community')" />
                    <span class="checkmark"></span>
                    <span class="layer-name">Sensors.community</span>
                  </label>
                  <button class="layer-about-btn" :class="{ active: expandedLayerAbout['sc'] }" @click.prevent.stop="expandedLayerAbout['sc'] = !expandedLayerAbout['sc']" title="About Sensors.community">
                    <i class="fas fa-question-circle"></i>
                  </button>
                </div>
                <p class="layer-description">Open citizen sensors — Brussels area ({{ scSensors.length }})</p>
                <Transition name="section-slide">
                  <div v-if="expandedLayerAbout['sc']" class="layer-about-panel">
                    <div class="layer-about-title">{{ SENSOR_INFO.sensors_community.title }}</div>
                    <p class="layer-about-text">{{ SENSOR_INFO.sensors_community.description }}</p>
                    <div class="layer-about-section uhi">
                      <strong><i class="fas fa-globe"></i> How it's used</strong>
                      <p>{{ SENSOR_INFO.sensors_community.details }}</p>
                    </div>
                  </div>
                </Transition>
                <!-- Dropdown list of Sensors.community sensors -->
                <Transition name="section-slide">
                  <div v-if="scVisible && scSensors.length > 0" class="sensor-station-list">
                    <div v-for="sensor in scSensors" :key="sensor.station_id" class="sensor-station-item">
                      <div class="sensor-station-header">
                        <span class="sensor-station-name">{{ sensor.station_name || 'SC-' + sensor.station_id }}</span>
                        <span class="sensor-station-temp" :style="{ color: tempColor(sensor.temperature) }">
                          {{ sensor.temperature != null ? sensor.temperature.toFixed(1) + '°C' : '--' }}
                        </span>
                      </div>
                      <div class="sensor-station-details">
                        <span v-if="sensor.humidity != null"><i class="fas fa-droplet"></i> {{ sensor.humidity.toFixed(0) }}%</span>
                        <span v-if="sensor.pressure != null"><i class="fas fa-gauge-high"></i> {{ sensor.pressure.toFixed(0) }} hPa</span>
                      </div>
                    </div>
                  </div>
                </Transition>
              </div>

              <!-- Sync info -->
              <div v-if="vlinderVisible || scVisible" class="sensor-sync-bar">
                <button class="sensor-sync-btn" @click="$emit('refresh-sensors')" title="Refresh all sensors">
                  <i class="fas fa-sync-alt"></i>
                </button>
                <span class="sensor-sync-label">
                  {{ vlinderSensors.length + scSensors.length }} sensor{{ (vlinderSensors.length + scSensors.length) !== 1 ? 's' : '' }}
                </span>
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
    buildingVisible: { type: Boolean, default: false },
    treeVisible: { type: Boolean, default: false },
    swipeEnabled: { type: Boolean, default: false },
    swipeLeftLayerId: { type: String, default: null },
    swipeRightLayerId: { type: String, default: null },
    uhiMin: { type: Number, default: null },
    uhiMax: { type: Number, default: null },
    predictionHistory: { type: Array, default: () => [] },
    vlinderSensors: { type: Array, default: () => [] },
    scSensors: { type: Array, default: () => [] },
    vlinderVisible: { type: Boolean, default: false },
    scVisible: { type: Boolean, default: false },
  })

  defineEmits([
    'toggle-layer', 'set-opacity', 'toggle-buildings', 'toggle-trees',
    'set-swipe-left', 'set-swipe-right',
    'layer-metadata', 'layer-download',
    'toggle-prediction-history', 'toggle-vlinder', 'toggle-sensors-community', 'refresh-sensors'
  ])

  const { getLegendStyle } = useLayerControls()

  const isPanelCollapsed = ref(false)
  const expandedLayerAbout = reactive({})

  const sections = reactive({
    uhi: true,
    mapLayers: false,
    tileset: false,
    realtime: true,
  })

  const LAYER_INFO = {
    uhi_prediction: {
      title: 'UHI Heat Risk Map',
      what: 'Shows the Urban Heat Island intensity prediction across Brussels, from cool (blue) to hot (red).',
      how: 'Machine learning model combining satellite imagery, land use, terrain data, and building geometry to predict heat island intensity.',
      uhi: 'This IS the UHI map — values represent the temperature excess above the ambient rural baseline . High values indicate areas that trap significantly more heat than surroundings.',
    },
    ndvi: {
      title: 'Normalized Difference Vegetation Index',
      what: 'Measures vegetation density and health from satellite imagery. Values range from -1 (no vegetation) to 1 (dense vegetation).',
      how: 'Calculated from the difference between near-infrared and red light reflectance: (NIR − Red) / (NIR + Red).',
      uhi: 'Vegetation provides cooling through evapotranspiration and shading. Higher NDVI areas are typically cooler — a key mitigation factor for UHI.',
    },
    ndwi: {
      title: 'Normalized Difference Water Index',
      what: 'Detects water presence in the landscape. Values range from -1 (dry) to 1 (water).',
      how: 'Calculated from green and near-infrared bands: (Green − NIR) / (Green + NIR).',
      uhi: 'Water bodies have high thermal inertia and provide evaporative cooling, reducing local temperatures. Proximity to water mitigates UHI effects.',
    },
    ndbi: {
      title: 'Normalized Difference Built-up Index',
      what: 'Measures the density of built-up/urbanized areas. Higher values = more built-up.',
      how: 'Calculated from shortwave infrared and near-infrared bands: (SWIR − NIR) / (SWIR + NIR).',
      uhi: 'Built-up surfaces absorb and retain heat, contributing to the urban heat island effect. Dense built-up areas are the primary driver of UHI.',
    },
    lst: {
      title: 'Land Surface Temperature',
      what: 'Surface temperature as measured by satellite. Shows how hot the ground surface is.',
      how: 'Derived from thermal infrared bands of satellite imagery (Landsat/Sentinel).',
      uhi: 'Direct measurement of surface heat — a key indicator of UHI intensity. Hot surfaces radiate heat to the surrounding air.',
    },
    dtm: {
      title: 'Digital Terrain Model',
      what: 'Bare ground elevation map, with buildings and vegetation removed.',
      how: 'Created from LiDAR data by filtering out above-ground objects.',
      uhi: 'Terrain affects air flow and cold air drainage patterns that influence local temperatures. Valleys can trap heat while ridges promote ventilation.',
    },
    dsm: {
      title: 'Digital Surface Model',
      what: 'Elevation including buildings and vegetation — the "visible" surface from above.',
      how: 'Created from LiDAR point clouds capturing the top of all surfaces.',
      uhi: 'Building height and density affect wind patterns, shading, and heat trapping in urban canyons. Tall buildings can both shade streets and trap heat.',
    },
    imperviousness: {
      title: 'Surface Imperviousness',
      what: 'Percentage of sealed/waterproof surfaces (concrete, asphalt). 0% = permeable, 100% = fully sealed.',
      how: 'Derived from satellite imagery classification of land cover types.',
      uhi: 'Impervious surfaces prevent water infiltration and evaporation, store heat during the day, and release it at night — a major UHI driver.',
    },
    albedo: {
      title: 'Surface Albedo',
      what: 'Surface reflectance — how much sunlight is reflected back. 0 = absorbs all, 1 = reflects all.',
      how: 'Measured from satellite multispectral imagery.',
      uhi: 'Low albedo (dark surfaces like asphalt) absorbs more solar radiation, heating up. High albedo materials (cool roofs, light pavement) help reduce UHI.',
    },
    rgb: {
      title: 'RGB Orthophoto',
      what: 'True-color aerial imagery of Brussels in visible light.',
      how: 'Captured by aerial surveys or satellites in Red, Green, Blue bands.',
      uhi: 'Provides visual context for interpreting other layers. Helps identify land cover types like parks, roads, and buildings.',
    },
    nir: {
      title: 'Near-Infrared Orthophoto',
      what: 'Aerial imagery in the near-infrared band (700-1100nm).',
      how: 'NIR light is strongly reflected by healthy vegetation and absorbed by water.',
      uhi: 'Vegetation appears bright in NIR, making it useful for assessing green coverage and vegetation health — both key UHI mitigators.',
    },
  }

  const TILESET_INFO = {
    buildings: {
      title: '3D Buildings',
      description: 'Interactive 3D building models of Brussels, sourced from Cesium Ion and snapped to terrain.',
      details: 'Building layout significantly affects heat trapping, wind flow, and shadowing patterns. Tall, dense buildings create "urban canyons" that trap heat and reduce ventilation — key factors in UHI formation. Use this layer to visualize building density and height across the city.',
    },
    trees: {
      title: '3D Trees',
      description: 'Interactive 3D tree models derived from LiDAR point cloud data.',
      details: 'Urban tree canopy is one of the most effective UHI mitigation strategies. Trees provide cooling through shade (reducing surface heating) and evapotranspiration (releasing water vapor that cools the air). This layer shows the spatial distribution of tree coverage.',
    },
  }

  const SENSOR_INFO = {
    vlinder: {
      title: 'VLINDER Weather Stations',
      description: 'Research-grade weather stations from the UGent VLINDER network in Flanders and Brussels. Each station measures temperature, humidity, wind speed, pressure and more.',
      details: 'VLINDER stations provide high-quality reference temperatures used to calibrate UHI intensity. Their geographic spread across the city helps validate heat island predictions against real ground-truth measurements.',
    },
    sensors_community: {
      title: 'Sensors.community',
      description: 'Open citizen science sensor network (formerly Luftdaten). Thousands of low-cost sensors deployed by citizens worldwide, measuring temperature, humidity and air quality.',
      details: 'These citizen-deployed sensors dramatically increase spatial coverage compared to official stations. While individual sensors are less precise, the dense network reveals fine-grained temperature patterns across neighborhoods — invaluable for UHI mapping.',
    },
  }

  function getLayersByCategory(category) {
    return props.layers.filter(layer => layer.category === category)
  }

  function tempColor(temp) {
    if (temp == null) return 'rgba(255,255,255,0.4)'
    if (temp < 5) return '#60a5fa'
    if (temp < 15) return '#4ade80'
    if (temp < 25) return '#fbbf24'
    return '#f87171'
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
