import * as Cesium from 'cesium'

/**
 * useCameraControls — Manages camera mode switching between 2D and 3D.
 *
 * Responsibilities:
 *  - In 2D mode: lock the camera to top-down, install a custom pan handler
 *    because Cesium's built-in translate handler behaves oddly when tilt is locked.
 *  - In 3D mode: restore full Cesium camera controls, enable atmosphere and buildings.
 *
 * @param {Object} options
 * @param {() => Cesium.Viewer}            options.getViewer          - Returns the Cesium viewer
 * @param {() => Cesium.Cesium3DTileset}   options.getBuildingTileset - Returns the building tileset (may be null)
 * @param {() => Cesium.Cesium3DTileset}   options.getTreeTileset     - Returns the tree tileset (may be null)
 * @param {Function}                       options.onSunSimRestore     - Callback to re-apply sun simulation in 3D
 */
export function useCameraControls({ getViewer, getBuildingTileset, getTreeTileset, onSunSimRestore }) {

  // Custom pan handler installed in 2D mode
  let manualPanHandler = null

  /**
   * Switch the viewer between '2D' (constrained top-down) and '3D' (full Cesium).
   *
   * @param {string} mode             - '2D' | '3D'
   * @param {boolean} sunSimEnabled   - Whether sun simulation is currently active
   * @param {number}  sunSimTime      - Current sun sim time in minutes since midnight
   */
  function updateViewMode(mode, sunSimEnabled, sunSimTime) {
    const viewer = getViewer()
    if (!viewer) return

    // Always destroy the custom pan handler before switching modes
    if (manualPanHandler) {
      manualPanHandler.destroy()
      manualPanHandler = null
    }

    if (mode === '2D') {
      _activate2DMode(viewer, sunSimEnabled)
    } else if (mode === '3D') {
      _activate3DMode(viewer, sunSimEnabled, sunSimTime)
    }
  }


  // ── Private helpers ─────────────────────────────────────────────────────────

  /**
   * Lock the camera to a strict top-down view and install a manual pan handler.
   */
  function _activate2DMode(viewer, sunSimEnabled) {
    const controller = viewer.scene.screenSpaceCameraController

    // Disable all rotational/tilt controls — only zoom is allowed natively
    controller.enableTilt = false
    controller.enableRotate = false
    controller.enableLook = false
    controller.enableTranslate = false
    controller.enableZoom = true

    controller.rotateEventTypes = []
    controller.tiltEventTypes = []
    controller.lookEventTypes = []
    controller.translateEventTypes = [Cesium.CameraEventType.LEFT_DRAG]

    // Snap camera to top-down, keeping the current ground position and altitude
    const focus = _getCameraFocusPoint(viewer)
    if (focus) {
      const carto = Cesium.Cartographic.fromCartesian(focus)
      const height = viewer.camera.positionCartographic.height

      viewer.camera.setView({
        destination: Cesium.Cartesian3.fromRadians(carto.longitude, carto.latitude, height),
        orientation: { heading: 0, pitch: -Cesium.Math.PI_OVER_TWO, roll: 0 }
      })
    }

    // Install custom drag-to-pan handler
    let isDragging = false
    let lastMousePosition = null

    manualPanHandler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)

    manualPanHandler.setInputAction((event) => {
      isDragging = true
      lastMousePosition = { x: event.position.x, y: event.position.y }
    }, Cesium.ScreenSpaceEventType.LEFT_DOWN)

    manualPanHandler.setInputAction((event) => {
      if (!isDragging || !lastMousePosition) return

      const pixelDx = event.endPosition.x - lastMousePosition.x
      const pixelDy = event.endPosition.y - lastMousePosition.y

      // Derive world-space meters per pixel from camera height + horizontal FOV.
      // No GPU readback needed — pure math on existing camera state.
      const height = viewer.camera.positionCartographic.height
      const fov = viewer.camera.frustum.fov || 1.0
      const metersPerPixel = (2 * height * Math.tan(fov / 2)) / viewer.scene.canvas.clientWidth

      viewer.camera.moveRight(-pixelDx * metersPerPixel)
      viewer.camera.moveUp(pixelDy * metersPerPixel)
      viewer.scene.requestRender()

      lastMousePosition.x = event.endPosition.x
      lastMousePosition.y = event.endPosition.y
    }, Cesium.ScreenSpaceEventType.MOUSE_MOVE)

    manualPanHandler.setInputAction(() => {
      isDragging = false
      lastMousePosition = null
    }, Cesium.ScreenSpaceEventType.LEFT_UP)

    // Clean cartographic rendering: no lighting, no fog, no 3D buildings
    if (!sunSimEnabled) viewer.scene.globe.enableLighting = false
    viewer.scene.fog.enabled = false

    const buildingTileset = getBuildingTileset()
    const treeTileset = getTreeTileset()
    if (buildingTileset) buildingTileset.show = false
    if (treeTileset) treeTileset.show = false
  }

  /**
   * Restore full 3D Cesium interaction: all camera controls, atmosphere, buildings.
   */
  function _activate3DMode(viewer, sunSimEnabled, sunSimTime) {
    const controller = viewer.scene.screenSpaceCameraController

    controller.rotateEventTypes = [Cesium.CameraEventType.LEFT_DRAG]
    controller.tiltEventTypes = [
      Cesium.CameraEventType.MIDDLE_DRAG,
      Cesium.CameraEventType.PINCH,
      { eventType: Cesium.CameraEventType.LEFT_DRAG,  modifier: Cesium.KeyboardEventModifier.CTRL },
      { eventType: Cesium.CameraEventType.RIGHT_DRAG, modifier: Cesium.KeyboardEventModifier.CTRL }
    ]
    controller.lookEventTypes = [
      { eventType: Cesium.CameraEventType.LEFT_DRAG, modifier: Cesium.KeyboardEventModifier.SHIFT }
    ]
    controller.translateEventTypes = [Cesium.CameraEventType.LEFT_DRAG]

    controller.enableTilt = true
    controller.enableRotate = true
    controller.enableLook = true
    controller.enableTranslate = true
    controller.enableZoom = true
    controller.enableRubberBandSelect = false

    viewer.scene.globe.enableLighting = sunSimEnabled
    viewer.scene.skyAtmosphere.show = true

    // Re-apply sun simulation state after switching to 3D
    if (sunSimEnabled) {
      onSunSimRestore(sunSimEnabled, sunSimTime)
    }

    // Fly slightly to trigger a re-render of the full 3D scene
    const focus = _getCameraFocusPoint(viewer)
    if (focus) {
      const carto = Cesium.Cartographic.fromCartesian(focus)
      const height = viewer.camera.positionCartographic.height

      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromRadians(carto.longitude, carto.latitude - 0.00005, height),
        orientation: { heading: Cesium.Math.toRadians(0), pitch: Cesium.Math.toRadians(-45), roll: 0 },
        duration: 0.5
      })
    }
  }

  /**
   * Pick the world point at the center of the screen.
   * Used to keep the camera centred on the same location when switching modes.
   *
   * @param {Cesium.Viewer} viewer
   * @returns {Cesium.Cartesian3 | null}
   */
  function _getCameraFocusPoint(viewer) {
    const scene = viewer.scene
    const center = new Cesium.Cartesian2(
      scene.canvas.clientWidth / 2,
      scene.canvas.clientHeight / 2
    )
    const ray = viewer.camera.getPickRay(center)
    return ray ? scene.globe.pick(ray, scene) : null
  }

  return { updateViewMode }
}
