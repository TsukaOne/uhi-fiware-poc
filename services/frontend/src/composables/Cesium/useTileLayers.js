import * as Cesium from 'cesium'

// Static PNG tiles exported by scripts/export_tiles.py, served by nginx
const TILES_URL = '/tiles'

// CARTO basemap, proxied by nginx which adds the API key server-side
const BASEMAP_URL = '/basemap/{z}/{x}/{y}.png'

// Bounding box of the Brussels-Capital Region: tiles only exist inside it.
const BRUSSELS_EXTENT = [4.20, 50.75, 4.50, 50.92]  // west, south, east, north

// Must match MIN_LEVEL / MAX_LEVEL / TILE_SIZE_PX of scripts/export_tiles.py.
// Rasters are 0.4 m/px: level 16 already reaches it, Cesium magnifies beyond.
const TILE_MIN_LEVEL = 10
const TILE_MAX_LEVEL = 16
const TILE_SIZE_PX = 512

/**
 * useTileLayers — Manages the map tile layers and the swipe/split-view feature.
 *
 * Responsibilities:
 *  - Add/remove/update tile layers onto the Cesium viewer
 *  - Configure the split-screen swipe comparison (left/right layer assignment)
 *  - Restore pre-swipe visibility state when swipe is disabled
 *
 * @param {Object} options
 * @param {() => Cesium.Viewer} options.getViewer - Returns the current Cesium viewer
 * @param {() => Array}  options.getLayerConfigs  - Returns the full layers array (for swipe lazy-load)
 */
export function useTileLayers({ getViewer, getLayerConfigs }) {

  // ── Internal state ──────────────────────────────────────────────────────────

  /** Map<layerId, Cesium.ImageryLayer> — tracks every loaded tile layer */
  const tileLayers = new Map()

  const errorReported = new Set()

  /** Whether swipe mode is currently active (used to guard one-time pre-swipe snapshot) */
  let swipeActive = false

  /**
   * Snapshot of layer visibility taken just before swipe was activated.
   * Used to restore the original state when swipe is turned off.
   * Map<layerId, boolean>
   */
  const preSwipeLayerShow = new Map()


  // ── Base imagery ────────────────────────────────────────────────────────────

  /**
   * Replace the default Cesium imagery with a light CartoDB basemap.
   * Called once during viewer initialization.
   */
  function setupImageryProviders() {
    const viewer = getViewer()
    viewer.imageryLayers.removeAll()

    const cartoDBProvider = new Cesium.UrlTemplateImageryProvider({
      url: BASEMAP_URL,
      credit: '© CartoDB'
    })
    viewer.imageryLayers.addImageryProvider(cartoDBProvider)
  }


  // ── Tile layer lifecycle ────────────────────────────────────────────────────

  /**
   * Load a tile layer and add it to the viewer.
   * No-op if the layer is already loaded.
   */
  function addTileLayer(layerConfig) {
    const viewer = getViewer()
    if (!viewer || tileLayers.has(layerConfig.id)) return

    const provider = new Cesium.UrlTemplateImageryProvider({
      url: `${TILES_URL}/${layerConfig.id}/{z}/{x}/{y}.png`,
      tilingScheme: new Cesium.GeographicTilingScheme(),
      credit: 'UHI Brussels - FARI',
      rectangle: Cesium.Rectangle.fromDegrees(...BRUSSELS_EXTENT),
      minimumLevel: TILE_MIN_LEVEL,
      maximumLevel: TILE_MAX_LEVEL,
      tileWidth: TILE_SIZE_PX,
      tileHeight: TILE_SIZE_PX,
    })

    // One warning per layer, not per failed tile
    provider.errorEvent.addEventListener((error) => {
      if (errorReported.has(layerConfig.id)) return
      errorReported.add(layerConfig.id)
      console.warn(
        `Tile layer "${layerConfig.id}" is failing to load tiles — were they exported?`,
        error?.message ?? error
      )
    })

    const imageryLayer = viewer.imageryLayers.addImageryProvider(provider)
    imageryLayer.alpha = layerConfig.opacity
    imageryLayer.show = true

    tileLayers.set(layerConfig.id, imageryLayer)
  }

  /**
   * Remove a tile layer from the viewer and drop it from the tracking map.
   */
  function removeTileLayer(layerId) {
    const viewer = getViewer()
    if (!viewer || !tileLayers.has(layerId)) return

    viewer.imageryLayers.remove(tileLayers.get(layerId))
    tileLayers.delete(layerId)
    errorReported.delete(layerId)
  }

  /**
   * Update the opacity (alpha) of a loaded tile layer.
   */
  function updateLayerOpacity(layerId, opacity) {
    if (!tileLayers.has(layerId)) return
    tileLayers.get(layerId).alpha = opacity
  }


  // ── Swipe / split-view ──────────────────────────────────────────────────────

  /**
   * Configure the Cesium split-view ("swipe") comparison mode.
   *
   * When enabled:
   *  - Snapshots current layer visibility (once, on first activation)
   *  - Lazy-loads left/right layers if not yet in the viewer
   *  - Assigns SplitDirection.LEFT / RIGHT; hides all other layers
   *
   * When disabled:
   *  - Restores original visibility from the snapshot
   *  - Removes layers that were loaded exclusively for the swipe session
   *
   * @param {boolean} enabled
   * @param {number}  position     - Normalized split position (0–1)
   * @param {string}  leftLayerId
   * @param {string}  rightLayerId
   */
  function updateSwipeConfig(enabled, position, leftLayerId, rightLayerId) {
    const viewer = getViewer()
    if (!viewer) return

    viewer.scene.splitPosition = enabled ? position : 1.0

    if (!enabled) {
      swipeActive = false

      // Restore pre-swipe visibility for every layer
      tileLayers.forEach((layer, id) => {
        layer.show = preSwipeLayerShow.has(id) ? preSwipeLayerShow.get(id) : false
        layer.splitDirection = Cesium.SplitDirection.NONE
      })

      // Unload layers that only exist because of this swipe session
      Array.from(preSwipeLayerShow.entries())
        .filter(([, wasVisible]) => !wasVisible)
        .forEach(([id]) => removeTileLayer(id))

      preSwipeLayerShow.clear()
      return
    }

    // First activation: snapshot current visibility before modifying anything
    if (!swipeActive) {
      swipeActive = true
      tileLayers.forEach((layer, id) => {
        preSwipeLayerShow.set(id, layer.show)
      })
    }

    // Lazy-load left/right layers in case they were not visible before swipe
    for (const layerId of [leftLayerId, rightLayerId]) {
      if (!layerId || tileLayers.has(layerId)) continue
      const config = getLayerConfigs().find(l => l.id === layerId)
      if (config) {
        addTileLayer(config)
        if (!preSwipeLayerShow.has(layerId)) preSwipeLayerShow.set(layerId, false)
      }
    }

    // Assign split directions: only left and right layers are visible
    tileLayers.forEach((layer, id) => {
      if (id === leftLayerId) {
        layer.show = true
        layer.splitDirection = Cesium.SplitDirection.LEFT
      } else if (id === rightLayerId) {
        layer.show = true
        layer.splitDirection = Cesium.SplitDirection.RIGHT
      } else {
        layer.show = false
        layer.splitDirection = Cesium.SplitDirection.NONE
      }
    })
  }


  // ── Cleanup ─────────────────────────────────────────────────────────────────

  /**
   * Remove all tracked tile layers from the viewer.
   * Called when the CesiumViewer component is unmounted.
   */
  function cleanup() {
    const viewer = getViewer()
    if (!viewer) return
    tileLayers.forEach(layer => viewer.imageryLayers.remove(layer))
    tileLayers.clear()
    errorReported.clear()
  }

  return {
    setupImageryProviders,
    addTileLayer,
    removeTileLayer,
    updateLayerOpacity,
    updateSwipeConfig,
    cleanup,
  }
}
