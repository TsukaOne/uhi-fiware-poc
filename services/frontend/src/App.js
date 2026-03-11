import { ref, reactive } from 'vue'

// ========================================
// VIEWPORT & LAYER STATE MANAGEMENT
// ========================================

export function useAppState() {
  // Navbar state
  const viewMode = ref('3D')
  const showLayers = ref(false)
  const showToolbox = ref(false)

  

  // 3D Tileset state
  const buildingVisible = ref(true)
  const treeVisible = ref(false)

  // Drawing state
  const drawingMode = ref(null) // 'polygon' | 'boundingBox' | null
  const showPredictMenu = ref(false)
  const drawnGeometries = ref([])

  // Swipe state
  const swipeEnabled = ref(false)
  const swipeLeftLayerId = ref(null)
  const swipeRightLayerId = ref(null)
  const swipePosition = ref(0.5)

  // Sun Simulation state
  const sunSimEnabled = ref(false)
  const sunSimTime = ref(720) // minutes since midnight, default = 12:00 noon

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
      visible: false,
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
    },
    {
      id: 'lst',
      name: 'LST',
      description: 'Land Surface Temperature',
      wmsLayer: 'uhi:lst',
      visible: false,
      opacity: 0.7,
      category: 'map_layers',
      legend: {
        min: { value: 0, color: '#313695', label: 'Cold' },
        max: { value: 254, color: '#a50026', label: 'Hot' }
      }
    },
    {
      id: 'dsm',
      name: 'DSM',
      description: 'Digital Surface Model (elevation + objects)',
      wmsLayer: 'uhi:dsm',
      visible: false,
      opacity: 0.7,
      category: 'map_layers',
      legend: {
        min: { value: 0, color: '#1a1a2e', label: '0 m' },
        max: { value: 220, color: '#ffffff', label: '220 m' }
      }
    },
    {
      id: 'ndbi',
      name: 'NDBI',
      description: 'Built-Up Index (-1 to 1)',
      wmsLayer: 'uhi:ndbi',
      visible: false,
      opacity: 0.7,
      category: 'map_layers',
      legend: {
        min: { value: -0.5, color: '#1a9641', label: 'Vegetation' },
        max: { value: 0.6, color: '#7b0f1a', label: 'Built-up' }
      }
    },
    {
      id: 'imperviousness',
      name: 'Imperviousness',
      description: 'Surface imperviousness (0-100%)',
      wmsLayer: 'uhi:imperviousness',
      visible: false,
      opacity: 0.7,
      category: 'map_layers',
      legend: {
        min: { value: 0, color: '#1a9850', label: 'Permeable' },
        max: { value: 100, color: '#d73027', label: 'Impervious' }
      }
    },
    {
      id: 'albedo',
      name: 'Albedo',
      description: 'Surface reflectance (0-1)',
      wmsLayer: 'uhi:albedo',
      visible: false,
      opacity: 0.7,
      category: 'map_layers',
      legend: {
        min: { value: 0, color: '#1a1a2e', label: 'Dark' },
        max: { value: 0.5, color: '#ffffff', label: 'Bright' }
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

  function toggleTrees() {
    treeVisible.value = !treeVisible.value
  }

  // ========================================
  // TOOL BOX  HANDLERS
  // ========================================

  function toggleToolbox() {
    showToolbox.value = !showToolbox.value
  }

  // ========================================
  // DRAWING HANDLERS
  // ========================================

  function togglePredictMenu() {
    showPredictMenu.value = !showPredictMenu.value
  }

  function startDrawingPolygon() {
    drawingMode.value = 'polygon'
    showPredictMenu.value = false
  }

  function startDrawingBoundingBox() {
    drawingMode.value = 'boundingBox'
    showPredictMenu.value = false
  }

  function stopDrawing() {
    drawingMode.value = null
  }

  function addGeometry(geometry) {
    drawnGeometries.value.push(geometry)
    console.log('Geometry added:', geometry)
  }

  function clearGeometries() {
    drawnGeometries.value = []
  }

  // ========================================
  // SWIPE HANDLERS
  // ========================================

  function toggleSwipe() {
    swipeEnabled.value = !swipeEnabled.value
    if (!swipeEnabled.value) {
      swipeLeftLayerId.value = null
      swipeRightLayerId.value = null
      swipePosition.value = 0.5
    }
  }

  // ========================================
  // SUN SIMULATION HANDLERS
  // ========================================

  function toggleSunSim() {
    sunSimEnabled.value = !sunSimEnabled.value
    if (!sunSimEnabled.value) {
      sunSimTime.value = 720
    }
  }

  function setSunSimTime(minutes) {
    sunSimTime.value = minutes
  }

  return {
    viewMode,
    showLayers,
    showToolbox,
    layers,
    activeLayers,
    buildingVisible,
    treeVisible,
    drawingMode,
    showPredictMenu,
    drawnGeometries,
    set2D,
    set3D,
    toggleLayersPanel,
    toggleLayer,
    setOpacity,
    toggleBuildings,
    toggleTrees,
    toggleToolbox,
    togglePredictMenu,
    startDrawingPolygon,
    startDrawingBoundingBox,
    stopDrawing,
    addGeometry,
    clearGeometries,
    swipeEnabled,
    swipeLeftLayerId,
    swipeRightLayerId,
    swipePosition,
    toggleSwipe,
    sunSimEnabled,
    sunSimTime,
    toggleSunSim,
    setSunSimTime
  }
}
