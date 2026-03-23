import * as Cesium from 'cesium'

/**
 * usePredictionOverlay — Displays a model prediction result as a georeferenced image overlay.
 *
 * The prediction service returns a PNG encoded as base64 with associated geographic bounds.
 * This composable converts it to a Cesium SingleTileImageryProvider and pins it to the map.
 *
 * Only one overlay is shown at a time: setting a new one removes the previous automatically.
 *
 * @param {Object} options
 * @param {() => Cesium.Viewer} options.getViewer - Returns the current Cesium viewer
 */
export function usePredictionOverlay({ getViewer }) {

  /** Reference to the currently displayed imagery layer (null when no overlay is active) */
  let predictionOverlayLayer = null


  /**
   * Display a prediction result as a georeferenced PNG overlay on the map.
   *
   * @param {Object|null} overlay
   * @param {string}  overlay.image_base64  - PNG image encoded as base64 (without data URI prefix)
   * @param {Object}  overlay.bounds        - Geographic extent: { west, south, east, north }
   * @param {Object}  [overlay.stats]       - Optional stats containing image_width / image_height
   *                                          for accurate tile dimensions
   */
  async function setPredictionOverlay(overlay) {
    const viewer = getViewer()

    // Remove any previous overlay before adding a new one
    if (predictionOverlayLayer) {
      viewer?.imageryLayers.remove(predictionOverlayLayer)
      predictionOverlayLayer = null
    }

    if (!overlay || !viewer) return

    const { image_base64, bounds, stats } = overlay
    const dataUrl = `data:image/png;base64,${image_base64}`
    const rect = Cesium.Rectangle.fromDegrees(bounds.west, bounds.south, bounds.east, bounds.north)

    try {
      // SingleTileImageryProvider.fromUrl is the modern async API (Cesium ≥ 1.104)
      // tileWidth/tileHeight must match the actual image dimensions for correct sampling
      const provider = await Cesium.SingleTileImageryProvider.fromUrl(dataUrl, {
        rectangle: rect,
        tileWidth:  stats?.image_width  || 256,
        tileHeight: stats?.image_height || 256,
      })

      predictionOverlayLayer = viewer.imageryLayers.addImageryProvider(provider)
      predictionOverlayLayer.alpha = 0.85
      predictionOverlayLayer.show = true
    } catch (err) {
      console.error('Failed to create prediction overlay:', err)
    }
  }


  /**
   * Remove the overlay from the viewer.
   * Called when the CesiumViewer component is unmounted.
   */
  function cleanup() {
    const viewer = getViewer()
    if (predictionOverlayLayer && viewer) {
      viewer.imageryLayers.remove(predictionOverlayLayer)
      predictionOverlayLayer = null
    }
  }

  return { setPredictionOverlay, cleanup }
}
