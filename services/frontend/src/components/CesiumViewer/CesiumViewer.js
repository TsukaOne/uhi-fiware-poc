import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as Cesium from 'cesium'

import { useDrawing }           from '../../composables/Cesium/useDrawing.js'
import { useWmsLayers }         from '../../composables/Cesium/useWmsLayers.js'
import { useCameraControls }    from '../../composables/Cesium/useCameraControls.js'
import { useSunSimulation }     from '../../composables/Cesium/useSunSimulation.js'
import { usePredictionOverlay } from '../../composables/Cesium/usePredictionOverlay.js'
import { useSensorMarkers }     from '../../composables/Cesium/useSensorMarkers.js'

// Brussels center — initial camera destination on startup
// height: 17 000 m gives a comfortable city-wide overview on first load
const BRUSSELS_CENTER = { longitude: 4.3817, latitude: 50.6403, height: 17_000 }

// 3D Buildings tileset URL (self-hosted on OVH S3)
const BUILDINGS_TILESET_URL = 'https://digitaltwin.s3.gra.io.cloud.ovh.net/tilesets_manager/1764770609672/tileset.json'

/**
 * useCesiumViewer — Main orchestrator for the Cesium 3D globe.
 *
 * This composable is intentionally thin: it initializes the viewer, wires the composables together, and manages Vue watchers. All domain logiclives in the dedicated composables imported above.
 *
 * @param {Object}   props - Vue component props (see CesiumViewer.vue)
 * @param {Function} emit  - Vue emit function
 */
export function useCesiumViewer(props, emit) {

  // ── Viewer state ──────────────────────
  const cesiumContainer = ref(null)
  let viewer = null
  let buildingTileset = null
  let treeTileset = null
  let treeLoaded = false


  // ── Composable wiring ──────────────────────────────────────────────────────

  const drawing = useDrawing({
    getViewer: () => viewer,
    emit,
  })

  const wmsLayers = useWmsLayers({
    getViewer:      () => viewer,
    getLayerConfigs: () => props.layers,
  })

  const sunSimulation = useSunSimulation({
    getViewer:         () => viewer,
    getBuildingTileset: () => buildingTileset,
  })

  const cameraControls = useCameraControls({
    getViewer:         () => viewer,
    getBuildingTileset: () => buildingTileset,
    getTreeTileset:    () => treeTileset,
    // Called by useCameraControls when switching back to 3D with sun sim active
    onSunSimRestore:   (enabled, time) => sunSimulation.update(enabled, time),
  })

  const predictionOverlay = usePredictionOverlay({
    getViewer: () => viewer,
  })

  const sensorMarkers = useSensorMarkers({
    getViewer: () => viewer,
    emit,
    getIsDrawing: drawing.getIsDrawing,
  })


  // ── Lifecycle ──────────────────────────────────────────────────────────────

  onMounted(async () => {
    await _initCesium()
  })

  onUnmounted(() => {
    _cleanupCesium()
  })


  // ── Initialization ─────────────────────────────────────────────────────────
  async function _initCesium() {

    viewer = new Cesium.Viewer(cesiumContainer.value, {
      baseLayerPicker:       false,
      geocoder:              true,
      homeButton:            false,
      sceneModePicker:       false,
      navigationHelpButton:  false,
      animation:             false,
      timeline:              false,
      fullscreenButton:      true,
      vrButton:              false,
      infoBox:               true,
      selectionIndicator:    false,
      shadows:               false,
      shouldAnimate:         false,
    })

    // Render on demand: only redraw when the scene actually changes
    viewer.scene.requestRenderMode = true
    viewer.scene.maximumRenderTimeChange = 0.1

    // Terrain — load once; fall back to ellipsoid if unavailable
    try {
      console.log('Loading Cesium World Terrain...')
      const terrain = await Cesium.createWorldTerrainAsync({
        requestWaterMask:    false,
        requestVertexNormals: false,
      })
      viewer.terrainProvider = terrain
    } catch (err) {
      console.warn('Failed to load Cesium World Terrain, using ellipsoid:', err)
    }

    // Depth testing ensures buildings sit on terrain rather than floating
    viewer.scene.globe.depthTestAgainstTerrain = true

    // Setup WMS layers before flying to the init view
    wmsLayers.setupImageryProviders()
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(
        BRUSSELS_CENTER.longitude,
        BRUSSELS_CENTER.latitude,
        BRUSSELS_CENTER.height
      ),
      orientation: {
        heading: Cesium.Math.toRadians(0),
        pitch:   Cesium.Math.toRadians(-40),
        roll:    0,
      },
      duration: 0,
    })

    // Load the building tileset immediately
    await _loadBuildingTileset()
    buildingTileset.show = false

    // Load WMS layers that are already marked as visible in props
    props.layers
      .filter(layer => layer.visible)
      .forEach(layer => wmsLayers.addWmsLayer(layer))

    // Sensor click handler needs a brief delay for the viewer canvas to be ready
    setTimeout(() => sensorMarkers.setupClickHandler(), 1000)
  }

  /**
   * Load the Brussels 3D building tileset from Cesium Ion.
   * Applies a set of performance tuning parameters (SSE, foveated rendering, cache).
   */
  async function _loadBuildingTileset() {
    try {
      buildingTileset = await Cesium.Cesium3DTileset.fromUrl(BUILDINGS_TILESET_URL)
      viewer.scene.primitives.add(buildingTileset)

      // Reduce quality during camera movement, restore when still
      buildingTileset.maximumScreenSpaceError = 32
      buildingTileset.foveatedScreenSpaceError = true
      buildingTileset.foveatedConeSize = 0.15
      buildingTileset.foveatedTimeDelay = 0.2
      buildingTileset.cacheBytes = 256 * 1024 * 1024
      buildingTileset.maximumCacheOverflowBytes = 128 * 1024 * 1024
      buildingTileset.depthFailMaterial = Cesium.Color.TRANSPARENT
      buildingTileset.dynamicScreenSpaceError = true
      buildingTileset.dynamicScreenSpaceErrorDensity = 0.00278
      buildingTileset.dynamicScreenSpaceErrorFactor = 4.0
      buildingTileset.dynamicScreenSpaceErrorHeightFalloff = 0.25
      buildingTileset.skipLevelOfDetail = true
      buildingTileset.baseScreenSpaceError = 1024
      buildingTileset.skipScreenSpaceErrorFactor = 16
      buildingTileset.skipLevels = 1
      buildingTileset.immediatelyLoadDesiredLevelOfDetail = false
      buildingTileset.cullRequestsWhileMoving = true
      buildingTileset.cullRequestsWhileMovingMultiplier = 60

      // Lower SSE while moving (better framerate), raise it when camera stops (full detail)
      viewer.camera.moveStart.addEventListener(() => {
        if (buildingTileset) buildingTileset.maximumScreenSpaceError = 64
        if (treeTileset)     treeTileset.maximumScreenSpaceError     = 96
      })
      viewer.camera.moveEnd.addEventListener(() => {
        if (buildingTileset) buildingTileset.maximumScreenSpaceError = 32
        if (treeTileset)     treeTileset.maximumScreenSpaceError     = 48
      })
    } catch (err) {
      console.warn('Failed to load building tileset:', err)
    }
  }

  /**
   * Lazy-load the vegetation tileset on first user activation.
   * Kept here (not in a composable) because it modifies the local treeTileset variable
   * shared with camera controls and building SSE handlers.
   */
  async function _loadTreeTileset() {
    try {
      treeTileset = await Cesium.Cesium3DTileset.fromUrl(
        "https://digitaltwin.s3.gra.io.cloud.ovh.net/tilesets_manager/3dtiles_vegetation_ds4/tileset.json"
      )
      treeTileset.maximumScreenSpaceError = 48
      treeTileset.foveatedScreenSpaceError = true
      treeTileset.foveatedConeSize = 0.15
      treeTileset.foveatedTimeDelay = 0.2
      treeTileset.cacheBytes = 128 * 1024 * 1024
      treeTileset.depthFailMaterial = Cesium.Color.TRANSPARENT
      treeTileset.dynamicScreenSpaceError = true
      treeTileset.dynamicScreenSpaceErrorDensity = 0.00278
      treeTileset.dynamicScreenSpaceErrorFactor = 4.0
      treeTileset.dynamicScreenSpaceErrorHeightFalloff = 0.25
      treeTileset.skipLevelOfDetail = true
      treeTileset.baseScreenSpaceError = 1024
      treeTileset.skipScreenSpaceErrorFactor = 16
      treeTileset.skipLevels = 1
      treeTileset.cullRequestsWhileMoving = true
      treeTileset.cullRequestsWhileMovingMultiplier = 60

      viewer.scene.primitives.add(treeTileset)
      treeLoaded = true
    } catch (err) {
      console.warn('Failed to load tree tileset:', err)
    }
  }


  // ── Cleanup ────────────────────────────────────────────────────────────────

  function _cleanupCesium() {
    predictionOverlay.cleanup()
    sensorMarkers.cleanup()
    wmsLayers.cleanup()

    if (viewer) {
      viewer.destroy()
      viewer = null
    }
  }


  // ── Vue watchers ───────────────────────────────────────────────────────────

  // View mode changes 
  watch(() => props.viewMode, (mode) => {
    cameraControls.updateViewMode(mode, props.sunSimEnabled, props.sunSimTime)
  })

  // Building tileset visibility - Loaded on init, toggle visibility with buildingVisible prop
  watch(() => props.buildingVisible, (isVisible) => {
    if (buildingTileset) {
      buildingTileset.show = isVisible
      console.log(`→ Buildings ${isVisible ? 'shown' : 'hidden'}`)
    }
  })

  // Lazy-load the tree tileset on first activation; toggle visibility afterward
  watch(() => props.treeVisible, async (isVisible) => {
    if (isVisible && !treeLoaded) {
      await _loadTreeTileset()
    } else if (treeTileset) {
      treeTileset.show = isVisible
    }
  })

  // React to layer visibility/opacity changes from the LayerControls panel
  watch(
    () => props.layers.map(l => ({ id: l.id, visible: l.visible, opacity: l.opacity })),
    (updatedLayers) => {
      updatedLayers.forEach(({ id, visible, opacity }) => {
        const layerConfig = props.layers.find(l => l.id === id)
        if (!layerConfig) return

        if (visible) {
          // addWmsLayer is a no-op if the layer is already loaded
          wmsLayers.addWmsLayer(layerConfig)
          wmsLayers.updateLayerOpacity(id, opacity)
        } else {
          // removeWmsLayer is a no-op if the layer is not loaded
          wmsLayers.removeWmsLayer(id)
        }
      })
    },
    { deep: true }
  )

  watch(() => props.drawingMode, (newMode) => {
    if (newMode) {
      drawing.startDrawing(newMode)
    } else {
      drawing.stopDrawing()
    }
  })

  // Swipe: react to enabled toggle or layer selection changes
  watch(
    [() => props.swipeEnabled, () => props.swipeLeftLayerId, () => props.swipeRightLayerId],
    ([enabled, leftId, rightId]) => {
      wmsLayers.updateSwipeConfig(enabled, props.swipePosition, leftId, rightId)
    }
  )

  // Swipe position: frequent updates during drag — kept separate for performance
  watch(() => props.swipePosition, (position) => {
    if (viewer && props.swipeEnabled) {
      viewer.scene.splitPosition = position
      viewer.scene.requestRender()
    }
  })

  watch(() => props.sunSimEnabled, (enabled) => {
    sunSimulation.update(enabled, props.sunSimTime)
  })

  watch(() => props.sunSimTime, (timeMinutes) => {
    if (props.sunSimEnabled) sunSimulation.update(true, timeMinutes)
  })

  watch(() => props.predictionOverlay, (overlay) => {
    predictionOverlay.setPredictionOverlay(overlay)
  })

  watch(
    [() => props.sensorData, () => props.sensorsVisible],
    ([sensors, visible]) => {
      sensorMarkers.updateMarkers(sensors, visible)
    },
    { deep: true }
  )


  // ── Public API (exposed to CesiumViewer.vue via defineExpose) ──────────────

  return {
    cesiumContainer,
    getViewer:     () => viewer,
    getTileset:    () => buildingTileset,
    undoLastPoint: drawing.undoLastPoint,
    flyTo: (longitude, latitude, height) => {
      if (viewer) {
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(longitude, latitude, height)
        })
      }
    },
  }
}
