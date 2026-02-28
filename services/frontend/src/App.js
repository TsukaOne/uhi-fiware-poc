import { ref, reactive } from 'vue'

// ========================================
// VIEWPORT & LAYER STATE MANAGEMENT
// ========================================

export function useAppState() {
  // Navbar state
  const viewMode = ref('3D')
  const showLayers = ref(true)
  const showToolbox = ref(false)
  
  // 3D Tileset state
  const buildingVisible = ref(true)

  // WMS layer definitions organized into categories
  const layers = reactive([
    // ========================================
    // SECTION A: URBAN HEAT ISLANDS MAPS
    // ========================================
    {
      id: 'uhi_prediction',
      name: 'UHI Heat Risk',
      description: 'Heat island prediction (0-1)',
      wmsLayer: 'uhi:uhi_prediction',
      visible: false,
      opacity: 0.7,
      category: 'uhi_maps',
      legend: {
        min: { value: 0, color: '#2166ac', label: 'Cool' },
        max: { value: 1, color: '#b2182b', label: 'Hot' }
      }
    },
    
    // ========================================
    // SECTION B: ADDITIONAL MAP LAYERS
    // ========================================
    {
      id: 'rgb',
      name: 'RGB Orthophoto',
      description: 'True color aerial imagery',
      wmsLayer: 'uhi:rgb',
      visible: false,
      opacity: 1.0,
      category: 'map_layers',
      legend: null
    },
    {
      id: 'nir',
      name: 'NIR Orthophoto',
      description: 'Near-infrared imagery',
      wmsLayer: 'uhi:nir',
      visible: false,
      opacity: 1.0,
      category: 'map_layers',
      legend: null
    },
    {
      id: 'ndvi',
      name: 'NDVI',
      description: 'Vegetation Index (-1 to 1)',
      wmsLayer: 'uhi:ndvi',
      visible: true,
      opacity: 0.7,
      category: 'map_layers',
      legend: {
        min: { value: -1, color: '#d73027', label: 'No vegetation' },
        max: { value: 1, color: '#1a9850', label: 'Dense vegetation' }
      }
    },
    {
      id: 'ndwi',
      name: 'NDWI',
      description: 'Water Index (-1 to 1)',
      wmsLayer: 'uhi:ndwi',
      visible: false,
      opacity: 0.7,
      category: 'map_layers',
      legend: {
        min: { value: -1, color: '#8c510a', label: 'No water' },
        max: { value: 1, color: '#01665e', label: 'Water' }
      }
    },
    {
      id: 'dtm',
      name: 'DTM',
      description: 'Digital Terrain Model',
      wmsLayer: 'uhi:dtm',
      visible: false,
      opacity: 0.7,
      category: 'map_layers',
      legend: {
        min: { value: 0, color: '#000000', label: 'Altitude 0' },
        max: { value: 129, color: '#ffffff', label: 'Altitude Max' }
      }
    }
  ])

  const activeLayers = ref(['ndvi'])

  // ========================================
  // VIEW MODE HANDLERS
  // ========================================

  function set2D() {
    viewMode.value = '2D'
  }

  function set3D() {
    viewMode.value = '3D'
  }

  function toggleLayersPanel() {
    showLayers.value = !showLayers.value
  }

  // ========================================
  // LAYER MANAGEMENT HANDLERS
  // ========================================

  function toggleLayer(layerId) {
    const layer = layers.find(l => l.id === layerId)
    if (layer) {
      layer.visible = !layer.visible
      if (layer.visible) {
        if (!activeLayers.value.includes(layerId)) {
          activeLayers.value.push(layerId)
        }
      } else {
        activeLayers.value = activeLayers.value.filter(id => id !== layerId)
      }
    }
  }

  function setOpacity(layerId, opacity) {
    const layer = layers.find(l => l.id === layerId)
    if (layer) {
      layer.opacity = opacity
    }
  }

  function toggleBuildings() {
    buildingVisible.value = !buildingVisible.value
  }

  // ========================================
  // TOOL BOX  HANDLERS
  // ========================================

  function toggleToolbox() {
    showToolbox.value = !showToolbox.value
  }

  return {
    viewMode,
    showLayers,
    showToolbox,
    layers,
    activeLayers,
    buildingVisible,
    set2D,
    set3D,
    toggleLayersPanel,
    toggleLayer,
    setOpacity,
    toggleBuildings,
    toggleToolbox
  }
}
