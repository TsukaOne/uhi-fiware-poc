import * as Cesium from 'cesium'

/**
 * usePixelClick — Intercepts left-clicks on the Cesium canvas to emit geographic coordinates.
 *
 * Responsibilities:
 *  - Resolve a screen click to geographic lon/lat (with terrain-aware ray picking)
 *  - Emit a 'pixel-click' event to the parent for downstream value queries
 *  - Suppress Cesium's default infoBox popup (we show our own PixelInfoPanel instead)
 *  - Guard against clicks that happen during an active drawing session
 *
 * @param {Object} options
 * @param {() => Cesium.Viewer} options.getViewer    - Returns the Cesium viewer
 * @param {Function}            options.emit         - Vue emit function for 'pixel-click'
 * @param {() => boolean}       options.getIsDrawing - Returns true while a drawing is in progress
 */
export function usePixelClick({ getViewer, emit, getIsDrawing }) {

  let pixelClickHandler = null


  /**
   * Register the click handler on the Cesium canvas.
   *
   * Must be called after the viewer has fully initialized (typically in a setTimeout
   * inside onMounted, because the viewer canvas is not ready immediately).
   *
   * Also suppresses the default Cesium entity selection popup: when the user clicks
   * on a WMS imagery layer, Cesium would try to show an infoBox. We intercept
   * selectedEntityChanged and immediately clear the selection.
   */
  function setup() {
    const viewer = getViewer()
    if (!viewer) return

    pixelClickHandler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)

    pixelClickHandler.setInputAction((click) => {
      // Do not intercept clicks while the user is actively drawing
      if (getIsDrawing()) return

      const cartesian = _pickPosition(viewer, click.position)
      if (!cartesian) return

      const cartographic = Cesium.Cartographic.fromCartesian(cartesian)

      emit('pixel-click', {
        lon:     Cesium.Math.toDegrees(cartographic.longitude),
        lat:     Cesium.Math.toDegrees(cartographic.latitude),
        screenX: click.position.x,
        screenY: click.position.y,
      })
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK)

    // Suppress the Cesium infoBox — we provide our own PixelInfoPanel overlay
    viewer.selectedEntityChanged.addEventListener(() => {
      viewer.selectedEntity = undefined
    })
  }

  /**
   * Destroy the click handler.
   * Called when the CesiumViewer component is unmounted.
   */
  function cleanup() {
    if (pixelClickHandler) {
      pixelClickHandler.destroy()
      pixelClickHandler = null
    }
  }


  // ── Private ─────────────────────────────────────────────────────────────────

  /**
   * Resolve a screen position to a Cesium Cartesian3 world coordinate.
   * Three-step fallback: pickPosition → globe.pick (ray) → pickEllipsoid.
   */
  function _pickPosition(viewer, screenPos) {
    let cartesian = viewer.scene.pickPosition(screenPos)
    if (!Cesium.defined(cartesian)) {
      const ray = viewer.camera.getPickRay(screenPos)
      if (ray) cartesian = viewer.scene.globe.pick(ray, viewer.scene)
    }
    if (!Cesium.defined(cartesian)) {
      cartesian = viewer.camera.pickEllipsoid(screenPos, viewer.scene.globe.ellipsoid)
    }
    return Cesium.defined(cartesian) ? cartesian : null
  }

  return { setup, cleanup }
}
