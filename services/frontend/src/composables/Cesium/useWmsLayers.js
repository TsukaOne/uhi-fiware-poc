import * as Cesium from 'cesium'

// GeoServer WMS endpoint
const GEOSERVER_URL = '/geoserver'

// Bounding box of the Brussels-Capital Region.
// Without it Cesium requests WMS tiles across the whole globe, most of which
// GeoServer answers with an empty image — hundreds of useless round-trips.
const BRUSSELS_EXTENT = [4.20, 50.75, 4.50, 50.92]  // west, south, east, north

// Source rasters are 10 m/px (see LAYER_RESOLUTION_M in PredictionPanel).
// Level 17 is already ~1 m/px — beyond that we would only magnify pixels.
const WMS_MIN_LEVEL = 10
const WMS_MAX_LEVEL = 17

// 512px tiles instead of the 256px default: ~4x fewer requests for the same area
const WMS_TILE_SIZE = 512

/**
 * useWmsLayers — Manages WMS imagery layers and the swipe/split-view feature.
 *
 * Responsibilities:
 *  - Add/remove/update WMS layers from GeoServer onto the Cesium viewer
 *  - Configure the split-screen swipe comparison (left/right layer assignment)
 *  - Restore pre-swipe visibility state when swipe is disabled
 *
 * @param {Object} options
 * @param {() => Cesium.Viewer} options.getViewer - Returns the current Cesium viewer
 * @param {() => Array}  options.getLayerConfigs  - Returns the full layers array (for swipe lazy-load)
 */
export function useWmsLayers({ getViewer, getLayerConfigs }) {

  // ── Internal state ──────────────────────────────────────────────────────────

  /** Map<layerId, Cesium.ImageryLayer> — tracks every loaded WMS layer */
  const wmsLayers = new Map()

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
      url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
      subdomains: ['a', 'b', 'c', 'd'],
      credit: '© CartoDB'
    })
    viewer.imageryLayers.addImageryProvider(cartoDBProvider)
  }


  // ── WMS layer lifecycle ─────────────────────────────────────────────────────

  /**
   * Load a WMS layer from GeoServer and add it to the viewer.
   * No-op if the layer is already loaded.
   */
  function addWmsLayer(layerConfig) {
    const viewer = getViewer()
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
      credit: 'UHI Brussels - FARI',
      rectangle: Cesium.Rectangle.fromDegrees(...BRUSSELS_EXTENT),
      minimumLevel: WMS_MIN_LEVEL,
      maximumLevel: WMS_MAX_LEVEL,
      tileWidth: WMS_TILE_SIZE,
      tileHeight: WMS_TILE_SIZE,
    })

    // One warning per layer, not per failed tile
    provider.errorEvent.addEventListener((error) => {
      if (errorReported.has(layerConfig.id)) return
      errorReported.add(layerConfig.id)
      console.warn(
        `WMS layer "${layerConfig.id}" is failing to load tiles — is GeoServer reachable?`,
        error?.message ?? error
      )
    })

    const imageryLayer = viewer.imageryLayers.addImageryProvider(provider)
    imageryLayer.alpha = layerConfig.opacity
    imageryLayer.show = true

    wmsLayers.set(layerConfig.id, imageryLayer)
  }

  /**
   * Remove a WMS layer from the viewer and drop it from the tracking map.
   */
  function removeWmsLayer(layerId) {
    const viewer = getViewer()
    if (!viewer || !wmsLayers.has(layerId)) return

    viewer.imageryLayers.remove(wmsLayers.get(layerId))
    wmsLayers.delete(layerId)
    errorReported.delete(layerId)
  }

  /**
   * Update the opacity (alpha) of a loaded WMS layer.
   */
  function updateLayerOpacity(layerId, opacity) {
    if (!wmsLayers.has(layerId)) return
    wmsLayers.get(layerId).alpha = opacity
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
      wmsLayers.forEach((layer, id) => {
        layer.show = preSwipeLayerShow.has(id) ? preSwipeLayerShow.get(id) : false
        layer.splitDirection = Cesium.SplitDirection.NONE
      })

      // Unload layers that only exist because of this swipe session
      Array.from(preSwipeLayerShow.entries())
        .filter(([, wasVisible]) => !wasVisible)
        .forEach(([id]) => removeWmsLayer(id))

      preSwipeLayerShow.clear()
      return
    }

    // First activation: snapshot current visibility before modifying anything
    if (!swipeActive) {
      swipeActive = true
      wmsLayers.forEach((layer, id) => {
        preSwipeLayerShow.set(id, layer.show)
      })
    }

    // Lazy-load left/right layers in case they were not visible before swipe
    for (const layerId of [leftLayerId, rightLayerId]) {
      if (!layerId || wmsLayers.has(layerId)) continue
      const config = getLayerConfigs().find(l => l.id === layerId)
      if (config) {
        addWmsLayer(config)
        if (!preSwipeLayerShow.has(layerId)) preSwipeLayerShow.set(layerId, false)
      }
    }

    // Assign split directions: only left and right layers are visible
    wmsLayers.forEach((layer, id) => {
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
   * Remove all tracked WMS layers from the viewer.
   * Called when the CesiumViewer component is unmounted.
   */
  function cleanup() {
    const viewer = getViewer()
    if (!viewer) return
    wmsLayers.forEach(layer => viewer.imageryLayers.remove(layer))
    wmsLayers.clear()
    errorReported.clear()
  }

  return {
    setupImageryProviders,
    addWmsLayer,
    removeWmsLayer,
    updateLayerOpacity,
    updateSwipeConfig,
    cleanup,
  }
}
