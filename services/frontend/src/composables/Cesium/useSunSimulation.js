import * as Cesium from 'cesium'

/**
 * useSunSimulation — Controls realistic sun positioning and shadow rendering.
 *
 * Responsibilities:
 *  - Enable/disable Cesium shadows and globe lighting
 *  - Map a "minutes since midnight" slider value to a Cesium clock time (JulianDate)
 *  - Trigger a micro camera fly to force Cesium to re-render the shadow pass
 *    (Cesium only redraws shadows when the camera moves or the clock ticks)
 *
 * @param {Object} options
 * @param {() => Cesium.Viewer}           options.getViewer          - Returns the Cesium viewer
 * @param {() => Cesium.Cesium3DTileset}  options.getBuildingTileset - Returns the building tileset (may be null)
 */
export function useSunSimulation({ getViewer, getBuildingTileset }) {

  /**
   * Enable or disable the sun simulation.
   *
   * When enabled:
   *  - Activates shadows on terrain, buildings, and the globe
   *  - Converts the slider value (minutes since midnight) to a real-world date/time
   *    using today's date + the slider hour:minute, then feeds it to Cesium's clock
   *  - Sets shadow quality parameters (size, softness, darkness)
   *
   * When disabled:
   *  - Turns off all shadow machinery
   *
   * @param {boolean} enabled
   * @param {number}  timeMinutes - Minutes since midnight (0 = 00:00, 720 = 12:00, 1440 = 24:00)
   */
  function update(enabled, timeMinutes) {
    const viewer = getViewer()
    if (!viewer) return

    const buildingTileset = getBuildingTileset()

    if (enabled) {
      console.log('→ SunSim enabled, updating sun position and shadows')

      viewer.shadows = true
      viewer.scene.globe.enableLighting = true
      viewer.terrainShadows = Cesium.ShadowMode.RECEIVE_ONLY

      if (buildingTileset) {
        buildingTileset.shadows = Cesium.ShadowMode.ENABLED
      }

      // Build a Date from today's calendar day + the slider hour/minute
      const now = new Date()
      const simDate = new Date(
        now.getFullYear(),
        now.getMonth(),
        now.getDate(),
        Math.floor(timeMinutes / 60),
        timeMinutes % 60,
        0
      )
      viewer.clock.currentTime = Cesium.JulianDate.fromDate(simDate)
      viewer.clock.shouldAnimate = false

      // High-quality shadow settings
      viewer.shadowMap.size = 2048
      viewer.shadowMap.softShadows = true
      viewer.shadowMap.darkness = 0.3

      // Force a re-render: Cesium won't update shadows unless the camera or clock moves
      _triggerCameraFly(viewer)
    } else {
      viewer.shadows = false
      viewer.scene.globe.enableLighting = false
      viewer.terrainShadows = Cesium.ShadowMode.DISABLED

      if (buildingTileset) {
        buildingTileset.shadows = Cesium.ShadowMode.DISABLED
      }

      viewer.clock.shouldAnimate = false

      _triggerCameraFly(viewer)
    }
  }

  /**
   * Perform an imperceptible camera move (pitch + 0.001 rad, duration 10ms).
   *
   * Why: Cesium's requestRenderMode only redraws when the scene is "dirty".
   * Shadow updates are not considered dirty by themselves — a camera move
   * is the cheapest way to invalidate the frame and force a shadow re-render.
   */
  function _triggerCameraFly(viewer) {
    viewer.camera.flyTo({
      destination: viewer.camera.position,
      orientation: {
        heading: viewer.camera.heading,
        pitch: viewer.camera.pitch + 0.001,
        roll: 0
      },
      duration: 0.01
    })
  }

  return { update }
}
