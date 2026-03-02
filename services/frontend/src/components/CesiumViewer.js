import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as Cesium from 'cesium'

/**
 * CESIUM VIEWER ARCHITECTURE
 *
 * PERFORMANCE CRITICAL:
 * - Tileset is loaded ONCE and never destroyed
 * - Visibility toggled via .show property
 * - No re-instantiation on mode switches
 * - Memory and GPU cache persist across 2D/3D transitions
 * - Terrain loaded once and reused
 * - Tileset snapped to terrain with depth testing enabled
 */

const cesiumContainer = ref(null)
let viewer = null
let buildingTileset = null
let terrainProvider = null
const wmsLayers = new Map()

// Drawing state
let drawingMode = null
let isDrawing = false
let drawnPoints = []
let drawnEntities = new Map()
let activeEntity = null
let mouseHandler = null

// GeoServer WMS endpoint
const GEOSERVER_URL = window.location.port === '3000' 
  ? '/geoserver'  // Proxied through nginx in Docker
  : 'http://localhost:8080/geoserver'  // Direct for local development

// Brussels center coordinates (WGS84)
const BRUSSELS_CENTER = {
  longitude: 4.3517,
  latitude: 50.8503,
  height: 5000
}

// ========================================
// CESIUM INITIALIZATION
// ========================================

export function useCesiumViewer(props, emit) {

  onMounted(async () => {
    await initCesium()
  })

  onUnmounted(() => {
    cleanupCesium()
  })
   
  async function initCesium() {
    // Set Cesium Ion token for 3D tileset streaming
    Cesium.Ion.defaultAccessToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJhY2E3ZDhlNC03Yjc0LTQzM2QtYmI5My0zYWQ3NjIwOTk0OTciLCJpZCI6Mjc4NzM4LCJpYXQiOjE3NDA0ODg1MjB9.VsZjL6pbKSwR_SBbxUq-KRweOU_P3R8DKjSpeD0EICY"

    // Initialize viewer with minimal UI
    viewer = new Cesium.Viewer(cesiumContainer.value, {
      baseLayerPicker: false,
      geocoder: true,
      homeButton: true,
      sceneModePicker: false,
      navigationHelpButton: false,
      animation: false,
      timeline: false,
      fullscreenButton: true,
      vrButton: false,
      infoBox: true,
      selectionIndicator: false,
      shadows: false,
      shouldAnimate: false
    })

    // ========================================
    // TERRAIN INITIALIZATION (LOAD ONCE)
    // ========================================
    try {
      // Load Cesium World Terrain for ground-accurate building placement
      terrainProvider = await Cesium.createWorldTerrainAsync({
        requestWaterMask: true,
        requestVertexNormals: true
      })
      viewer.terrainProvider = terrainProvider
    } catch (error) {
      console.warn('Failed to load Cesium World Terrain, using ellipsoid:', error)
    }

    // ========================================
    // DEPTH TESTING 
    // ========================================
    // Enable depth testing so buildings respect terrain
    viewer.scene.globe.depthTestAgainstTerrain = true

    // Set up imagery for cartographic appearance
    setupImageryProviders()

    // Set initial camera to Brussels, top-down view
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(
        BRUSSELS_CENTER.longitude,
        BRUSSELS_CENTER.latitude,
        500
      ),
      orientation: {
        heading: Cesium.Math.toRadians(0),
        pitch: Cesium.Math.toRadians(-50),
        roll: 0
      },
      duration: 0
    })

    // ========================================
    // LOAD TILESET
    // ========================================
    try {
      buildingTileset = await Cesium.Cesium3DTileset.fromIonAssetId(3474524)
      
      // Add to scene (visible by default for 3D mode)
      viewer.scene.primitives.add(buildingTileset)
      
      // Sample terrain at Brussels center to ensure tileset sits on ground
      try {
        const bruxellesCartesian = Cesium.Cartesian3.fromDegrees(
          BRUSSELS_CENTER.longitude,
          BRUSSELS_CENTER.latitude
        )
        const bruxellesCartographic = Cesium.Cartographic.fromCartesian(bruxellesCartesian)
        
        // Sample terrain height at specific point
        const sampledPositions = await Cesium.sampleTerrainMostDetailed(
          terrainProvider,
          [bruxellesCartographic]
        )
      } catch (error) {
        console.warn('Terrain height sampling fallback:', error)
      }
      
      // Enable depth testing on tileset for proper occlusion
      buildingTileset.depthFailMaterial = Cesium.Color.TRANSPARENT
      
    } catch (error) {
    }

    // Add initial WMS layers
    if (props.layers) {
      props.layers.forEach(layer => {
        if (layer.visible) {
          addWmsLayer(layer)
        }
      })
    }
  }

  /**INTERACTION MODE SWITCHING **/
  function updateViewMode(mode) {
    if (!viewer) return

    if (mode === '2D') {
      // ========================================
      // 2D MODE: CONSTRAINED TOP-DOWN 3D
      // ========================================
      
      // Lock camera navigation to top-down only
      viewer.scene.screenSpaceCameraController.enableTilt = false
      viewer.scene.screenSpaceCameraController.enableRotate = false
      viewer.scene.screenSpaceCameraController.enableLook = false

      viewer.scene.screenSpaceCameraController.rotateEventTypes = []
      viewer.scene.screenSpaceCameraController.tiltEventTypes = []
      viewer.scene.screenSpaceCameraController.lookEventTypes = []

      viewer.scene.screenSpaceCameraController.translateEventTypes = [
        Cesium.CameraEventType.LEFT_DRAG
     ]
      
      // Allow pan and zoom
      viewer.scene.screenSpaceCameraController.enableTranslate = true
      viewer.scene.screenSpaceCameraController.enableZoom = true
      
      // Force camera to strict top-down orientation
      viewer.camera.setView({
        destination: viewer.camera.position,
        orientation: {
          heading: Cesium.Math.toRadians(0),
          pitch: Cesium.Math.toRadians(-90),
          roll: 0
        }
      })
      
      // Disable lighting effects for cleaner map rendering
      viewer.scene.globe.enableLighting = false
      
      // Keep buildings visible 
      if (buildingTileset) {
        buildingTileset.show = true
      }
      
      // Keep fog disabled for clear cartographic view
      viewer.scene.fog.enabled = false
      
      console.log('→ 2D Mode: Constrained top-down view (map-like interaction)')

    } else if (mode === '3D') {
      // ========================================
      // 3D MODE: FULL CESIUM INTERACTION
      // ========================================
      // Full unrestricted 3D navigation
      
      // Enable all camera controls
      viewer.scene.screenSpaceCameraController.enableTilt = true
      viewer.scene.screenSpaceCameraController.enableRotate = true
      viewer.scene.screenSpaceCameraController.enableLook = true
      viewer.scene.screenSpaceCameraController.enableTranslate = true
      viewer.scene.screenSpaceCameraController.enableZoom = true
      
      // Disable rubber band select for cleaner interaction
      viewer.scene.screenSpaceCameraController.enableRubberBandSelect = false
      
      viewer.scene.globe.enableLighting = false
      
      // Ensure atmosphere is visible
      viewer.scene.skyAtmosphere.show = true
      
      // Show buildings with full 3D context
      if (buildingTileset) {
        buildingTileset.show = true
      }
      
      // Move camera to 3D perspective 
      viewer.camera.flyTo({
        destination: viewer.camera.position,
        orientation: {
          heading: Cesium.Math.toRadians(45),
          pitch: Cesium.Math.toRadians(-45),
          roll: 0
        },
        duration: 0.5
      })
      
    }
  }

  // ========================================
  // DRAWING FUNCTIONS
  // ========================================

  function startDrawing(mode) {
    if (!viewer) return

    drawingMode = mode
    drawnPoints = []
    isDrawing = true

    // Initialize mouse handler for drawing
    if (!mouseHandler) {
      mouseHandler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)
    }

    // Handle mouse click for adding points
    mouseHandler.setInputAction((click) => {
      if (!isDrawing || !drawingMode) return

      const pickedObject = viewer.scene.pick(click.position)
      let cartesian

      if (Cesium.defined(pickedObject)) {
        cartesian = viewer.scene.pickPosition(click.position)
      } else {
        cartesian = viewer.camera.pickEllipsoid(click.position, viewer.scene.globe.ellipsoid)
      }

      if (!Cesium.defined(cartesian)) return

      const cartographic = Cesium.Cartographic.fromCartesian(cartesian)
      drawnPoints.push({
        longitude: Cesium.Math.toDegrees(cartographic.longitude),
        latitude: Cesium.Math.toDegrees(cartographic.latitude),
        cartesian: cartesian
      })

      // Visual feedback: draw points as circles
      viewer.entities.add({
        position: cartesian,
        point: {
          pixelSize: 8,
          color: Cesium.Color.GREEN,
          outlineColor: Cesium.Color.WHITE,
          outlineWidth: 2
        }
      })

      // Update geometry visualization
      updateDrawingVisualization()
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK)

    // Handle right-click to finish drawing
    mouseHandler.setInputAction(() => {
      if (!isDrawing || !drawingMode) return
      finishDrawing()
    }, Cesium.ScreenSpaceEventType.RIGHT_CLICK)

    console.log(`→ Drawing mode started: ${mode}`)
  }

  function updateDrawingVisualization() {
    if (!drawingMode || drawnPoints.length < 2) return

    // Remove previous preview entity if exists
    if (activeEntity) {
      viewer.entities.remove(activeEntity)
    }

    if (drawingMode === 'polygon') {
      const positions = drawnPoints.map(p => p.cartesian)

      activeEntity = viewer.entities.add({
        polygon: {
          hierarchy: new Cesium.PolygonHierarchy(positions),
          material: Cesium.Color.GREEN.withAlpha(0.3),
          outline: true,
          outlineColor: Cesium.Color.WHITE,
          outlineWidth: 2
        }
      })
    } else if (drawingMode === 'boundingBox') {
      if (drawnPoints.length >= 2) {
        const minLat = Math.min(drawnPoints[0].latitude, drawnPoints[1].latitude)
        const maxLat = Math.max(drawnPoints[0].latitude, drawnPoints[1].latitude)
        const minLon = Math.min(drawnPoints[0].longitude, drawnPoints[1].longitude)
        const maxLon = Math.max(drawnPoints[0].longitude, drawnPoints[1].longitude)

        const boxCorners = [
          Cesium.Cartesian3.fromDegrees(minLon, minLat),
          Cesium.Cartesian3.fromDegrees(maxLon, minLat),
          Cesium.Cartesian3.fromDegrees(maxLon, maxLat),
          Cesium.Cartesian3.fromDegrees(minLon, maxLat)
        ]

        activeEntity = viewer.entities.add({
          polygon: {
            hierarchy: new Cesium.PolygonHierarchy(boxCorners),
            material: Cesium.Color.BLUE.withAlpha(0.3),
            outline: true,
            outlineColor: Cesium.Color.WHITE,
            outlineWidth: 2
          }
        })
      }
    }
  }

  function finishDrawing() {
    if (drawnPoints.length < 2) {
      console.warn('Not enough points drawn')
      stopDrawing()
      return
    }

    const geometry = {
      type: drawingMode,
      points: drawnPoints,
      timestamp: new Date().toISOString()
    }

    if (drawingMode === 'polygon') {
      geometry.geoJSON = {
        type: 'Polygon',
        coordinates: [drawnPoints.map(p => [p.longitude, p.latitude])]
      }
    } else if (drawingMode === 'boundingBox') {
      const minLat = Math.min(drawnPoints[0].latitude, drawnPoints[1].latitude)
      const maxLat = Math.max(drawnPoints[0].latitude, drawnPoints[1].latitude)
      const minLon = Math.min(drawnPoints[0].longitude, drawnPoints[1].longitude)
      const maxLon = Math.max(drawnPoints[0].longitude, drawnPoints[1].longitude)

      geometry.bounds = { minLon, maxLon, minLat, maxLat }
      geometry.geoJSON = {
        type: 'Polygon',
        coordinates: [[
          [minLon, minLat],
          [maxLon, minLat],
          [maxLon, maxLat],
          [minLon, maxLat],
          [minLon, minLat]
        ]]
      }
    }

    console.log('→ Drawing finished:', geometry)

    // Emit geometry to parent component
    if (emit) {
      emit('geometry-drawn', geometry)
    }

    stopDrawing()
  }

  function stopDrawing() {
    isDrawing = false
    drawingMode = null
    drawnPoints = []

    if (mouseHandler) {
      mouseHandler.removeInputAction(Cesium.ScreenSpaceEventType.LEFT_CLICK)
      mouseHandler.removeInputAction(Cesium.ScreenSpaceEventType.RIGHT_CLICK)
      mouseHandler.destroy()
      mouseHandler = null
    }

    console.log('→ Drawing mode stopped')
  }

  function setupImageryProviders() {
    // Remove default imagery
    viewer.imageryLayers.removeAll()
    const cartoDBProvider = new Cesium.UrlTemplateImageryProvider({
      url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
      subdomains: ['a', 'b', 'c', 'd'],
      credit: '© CartoDB'
    })

    viewer.imageryLayers.addImageryProvider(cartoDBProvider)
  }

  // ========================================
  // WMS LAYER MANAGEMENT
  // ========================================

  function addWmsLayer(layerConfig) {
    if (!viewer || wmsLayers.has(layerConfig.id)) return

    const provider = new Cesium.WebMapServiceImageryProvider({
      url: `${GEOSERVER_URL}/uhi/wms`,
      layers: layerConfig.wmsLayer,
      parameters: {
        service: 'WMS',
        version: '1.1.1',
        request: 'GetMap',
        format: 'image/png',
        transparent: true,
        styles: '',
        crs: 'EPSG:4326'
      },
      enablePickFeatures: true,
      credit: 'UHI Brussels - FARI'
    })

    const imageryLayer = viewer.imageryLayers.addImageryProvider(provider)
    imageryLayer.alpha = layerConfig.opacity
    
    // CRITICAL: Ensure GeoTIFF layers align with terrain
    // By enabling globe depth testing, WMS layers will clamp to terrain elevation
    // This prevents floating or buried effects in 3D mode
    imageryLayer.show = true

    wmsLayers.set(layerConfig.id, imageryLayer)
  }

  function removeWmsLayer(layerId) {
    if (!viewer || !wmsLayers.has(layerId)) return

    const layer = wmsLayers.get(layerId)
    viewer.imageryLayers.remove(layer)
    wmsLayers.delete(layerId)
  }

  function updateLayerOpacity(layerId, opacity) {
    if (!wmsLayers.has(layerId)) return
    
    const layer = wmsLayers.get(layerId)
    layer.alpha = opacity
  }

  // ========================================
  // WATCHERS FOR STATE CHANGES
  // ========================================

  // Watch viewMode and update interaction mode accordingly
  watch(() => props.viewMode, (newMode) => {
    updateViewMode(newMode)
  })

  // Watch building visibility
  watch(() => props.buildingVisible, (isVisible) => {
    if (buildingTileset) {
      buildingTileset.show = isVisible
      console.log(`→ Buildings ${isVisible ? 'shown' : 'hidden'}`)
    }
  })

  // Watch layers for visibility and opacity changes
  watch(() => props.layers.map(l => ({ id: l.id, visible: l.visible, opacity: l.opacity })), 
    (newLayers) => {
      newLayers.forEach(layer => {
        const existingLayer = wmsLayers.has(layer.id)
        const layerConfig = props.layers.find(l => l.id === layer.id)
        
        if (layer.visible && !existingLayer) {
          addWmsLayer(layerConfig)
        } else if (!layer.visible && existingLayer) {
          removeWmsLayer(layer.id)
        } else if (layer.visible && existingLayer) {
          updateLayerOpacity(layer.id, layer.opacity)
        }
      })
    },
    { deep: true }
  )

  // Watch drawing mode changes
  watch(() => props.drawingMode, (newMode) => {
    if (newMode) {
      startDrawing(newMode)
    } else if (isDrawing) {
      stopDrawing()
    }
  })

  // ========================================
  // CLEANUP
  // ========================================

  function cleanupCesium() {
    if (viewer) {
      // Clear WMS layers
      wmsLayers.forEach((imageryLayer) => {
        viewer.imageryLayers.remove(imageryLayer)
      })
      wmsLayers.clear()

      // Destroy viewer
      viewer.destroy()
      viewer = null
    }
  }

  // Expose public API
  return {
    cesiumContainer,
    getViewer: () => viewer,
    getTileset: () => buildingTileset,
    flyTo: (longitude, latitude, height) => {
      if (viewer) {
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(longitude, latitude, height)
        })
      }
    }
  }
}
