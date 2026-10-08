import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as Cesium from 'cesium'

import { useDrawing }           from '../../composables/Cesium/useDrawing.js'
import { useTileLayers }        from '../../composables/Cesium/useTileLayers.js'
import { useCameraControls }    from '../../composables/Cesium/useCameraControls.js'
import { useSunSimulation }     from '../../composables/Cesium/useSunSimulation.js'
import { usePredictionOverlay } from '../../composables/Cesium/usePredictionOverlay.js'
import { useSensorMarkers }     from '../../composables/Cesium/useSensorMarkers.js'
import { useFlyMode }           from '../../composables/Cesium/useFlyMode.js'
import { useRoofFunctions }     from '../../composables/Cesium/useRoofFunctions.js'

// Brussels center — initial camera destination on startup
// height: 17 000 m gives a comfortable city-wide overview on first load
const BRUSSELS_CENTER = { longitude: 4.3817, latitude: 50.6403, height: 17_000 }

// 3D Buildings tileset URL (self-hosted on OVH S3)
const BUILDINGS_TILESET_URL = 'https://digitaltwin.s3.gra.io.cloud.ovh.net/tilesets_manager/1764770609672/tileset.json'

const TILESET_CULL_ALTITUDE = 6_000
const TILESET_SSE_BY_ALTITUDE = [
  { maxAltitude: 600,   buildings: 32,  trees: 48 },
  { maxAltitude: 2_000, buildings: 64,  trees: 96 },
  { maxAltitude: Infinity, buildings: 128, trees: 192 },
]

// Quality is halved while the camera moves, then restored once it settles
const MOVING_SSE_FACTOR = 2

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

  // Whether the user asked for each tileset. The altitude guard below may still
  // hide them, so `tileset.show` alone is not a reliable record of user intent.
  let buildingsWanted = props.buildingVisible
  let treesWanted = props.treeVisible

  // True between camera moveStart and moveEnd
  let cameraIsMoving = false


  // ── Composable wiring ──────────────────────────────────────────────────────

  const drawing = useDrawing({
    getViewer: () => viewer,
    emit,
  })

  const tileLayers = useTileLayers({
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
    // Called when returning to 3D, so tilesets hidden by 2D mode come back
    onRestoreTilesets: () => _applyTilesetLod(),
  })

  const roofFunctions = useRoofFunctions({
    getBuildingTileset: () => buildingTileset,
    getViewer:          () => viewer,
  })

  const flyMode = useFlyMode({
    getViewer:    () => viewer,
    getIsDrawing: drawing.getIsDrawing,
    onExit:       () => emit('exit-fly-mode'),
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

    // ── Rendering cost ──
    // MSAA is on by default when the context supports it: 4x the fragment work
    // for a marginal gain on building facades. This is the single cheapest win
    // when the 3D tilesets are visible.
    viewer.scene.msaaSamples = 1
    viewer.scene.postProcessStages.fxaa.enabled = false
    viewer.scene.globe.showGroundAtmosphere = false

    // Fog is not cosmetic here: it is what feeds the tilesets'
    // dynamicScreenSpaceError, letting distant tiles degrade.
    viewer.scene.fog.enabled = true
    viewer.scene.fog.density = 0.0002

    // Only fires once the camera has moved appreciably — cheap enough to drive
    // the tileset LOD from.
    viewer.camera.percentageChanged = 0.2
    viewer.camera.changed.addEventListener(_applyTilesetLod)

    viewer.camera.moveStart.addEventListener(() => {
      cameraIsMoving = true
      _applyTilesetLod()
    })
    viewer.camera.moveEnd.addEventListener(() => {
      cameraIsMoving = false
      _applyTilesetLod()
    })

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

    // Setup the basemap before flying to the init view
    tileLayers.setupImageryProviders()
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
    _applyTilesetLod()
    if (props.roofFunctionsVisible) roofFunctions.enable()

    // Load tile layers that are already marked as visible in props
    props.layers
      .filter(layer => layer.visible)
      .forEach(layer => tileLayers.addTileLayer(layer))

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

      // Base quality; _applyTilesetLod() overrides it from the camera altitude
      buildingTileset.maximumScreenSpaceError = 32
      buildingTileset.foveatedScreenSpaceError = true
      buildingTileset.foveatedConeSize = 0.15
      buildingTileset.foveatedTimeDelay = 0.2
      // A hidden tileset keeps downloading unless told otherwise — and with the
      // altitude guard it is hidden a lot of the time.
      buildingTileset.preloadWhenHidden = false
      buildingTileset.preloadFlightDestinations = false
      buildingTileset.cacheBytes = 128 * 1024 * 1024
      buildingTileset.maximumCacheOverflowBytes = 64 * 1024 * 1024
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
      treeTileset.preloadWhenHidden = false
      treeTileset.preloadFlightDestinations = false
      treeTileset.cacheBytes = 96 * 1024 * 1024
      treeTileset.maximumCacheOverflowBytes = 48 * 1024 * 1024
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
      _applyTilesetLod()
    } catch (err) {
      console.warn('Failed to load tree tileset:', err)
    }
  }

  /**
   * Reconcile both 3D tilesets with the current camera altitude and the user's
   * layer choices.
   *
   * Visibility is `wanted && low enough` — the altitude guard never overwrites
   * the checkbox state, it only suppresses rendering where the tiles would be
   * invisible anyway. Called on camera change, on move start/end, on load, and
   * when returning from 2D mode.
   */
  function _applyTilesetLod() {
    if (!viewer || viewer.isDestroyed()) return
    if (!buildingTileset && !treeTileset) return

    // 2D mode deliberately hides both tilesets; leave it alone
    if (props.viewMode === '2D') return

    const altitude = viewer.camera.positionCartographic.height
    const withinRange = altitude <= TILESET_CULL_ALTITUDE
    const tier = TILESET_SSE_BY_ALTITUDE.find(t => altitude <= t.maxAltitude)
    const factor = cameraIsMoving ? MOVING_SSE_FACTOR : 1

    if (buildingTileset) {
      buildingTileset.show = buildingsWanted && withinRange
      buildingTileset.maximumScreenSpaceError = tier.buildings * factor
    }
    if (treeTileset) {
      treeTileset.show = treesWanted && withinRange
      treeTileset.maximumScreenSpaceError = tier.trees * factor
    }

    // Terrain and tilesets compete for the same bandwidth; ease off the globe
    // while buildings are on screen.
    viewer.scene.globe.maximumScreenSpaceError =
      (buildingTileset?.show || treeTileset?.show) ? 3 : 2
  }


  // ── Cleanup ────────────────────────────────────────────────────────────────

  function _cleanupCesium() {
    flyMode.disable()
    roofFunctions.disable()
    drawing.stopDrawing()
    predictionOverlay.cleanup()
    sensorMarkers.cleanup()
    tileLayers.cleanup()

    if (viewer) {
      viewer.destroy()
      viewer = null
    }
  }


  // ── Vue watchers ───────────────────────────────────────────────────────────

  // View mode changes — '2D' | '3D' | 'FLY'
  watch(() => props.viewMode, (mode) => {
    // Always leave free flight first: it owns the camera controller and the
    // render mode, and must restore them before anything else touches them.
    flyMode.disable()

    if (mode === 'FLY') {
      // Free flight is 3D with a different driver — reuse the 3D setup, then
      // take the camera over.
      cameraControls.updateViewMode('3D', props.sunSimEnabled, props.sunSimTime)
      flyMode.enable()
    } else {
      cameraControls.updateViewMode(mode, props.sunSimEnabled, props.sunSimTime)
    }
  })

  // Building tileset visibility - Loaded on init, toggle visibility with buildingVisible prop
  watch(() => props.buildingVisible, (isVisible) => {
    buildingsWanted = isVisible
    _applyTilesetLod()
  })

  // Multiroof rooftop colour coding (illustrative — see useRoofFunctions.js)
  watch(() => props.roofFunctionsVisible, (isVisible) => {
    if (isVisible) roofFunctions.enable()
    else roofFunctions.disable()
  })

  // Lazy-load the tree tileset on first activation; toggle visibility afterward
  watch(() => props.treeVisible, async (isVisible) => {
    treesWanted = isVisible
    if (isVisible && !treeLoaded) {
      await _loadTreeTileset()
    } else {
      _applyTilesetLod()
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
          // addTileLayer is a no-op if the layer is already loaded
          tileLayers.addTileLayer(layerConfig)
          tileLayers.updateLayerOpacity(id, opacity)
        } else {
          // removeTileLayer is a no-op if the layer is not loaded
          tileLayers.removeTileLayer(id)
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
      tileLayers.updateSwipeConfig(enabled, props.swipePosition, leftId, rightId)
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
    getFlyTelemetry: flyMode.getTelemetry,
    flyTo: (longitude, latitude, height) => {
      if (viewer) {
        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(longitude, latitude, height)
        })
      }
    },
  }
}
