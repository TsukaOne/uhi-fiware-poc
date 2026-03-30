import * as Cesium from 'cesium'

/**
 * useSensorMarkers — Displays temperature sensor stations as color-coded dots on the Cesium globe.
 *
 * Each sensor with valid coordinates gets a point whose color reflects its temperature.
 * Clicking a dot emits a 'sensor-click' event with the sensor data + screen position
 * so the parent can show a metadata popup.
 *
 * @param {Object}        options
 * @param {() => Cesium.Viewer} options.getViewer    - Returns the current Cesium viewer
 * @param {Function}            options.emit         - Vue emit function for 'sensor-click'
 * @param {() => boolean}       options.getIsDrawing - Returns true while a drawing is in progress
 */
export function useSensorMarkers({ getViewer, emit, getIsDrawing }) {

  /** Map of station_id → { entity, sensorData } */
  const markerEntities = new Map()
  let clickHandler = null

  /**
   * Update sensor markers on the map.
   * @param {Array}   sensors - Array of sensor objects
   * @param {boolean} visible - Whether markers should be shown
   */
  function updateMarkers(sensors, visible) {
    const viewer = getViewer()
    if (!viewer) return

    const currentIds = new Set(sensors.map(s => s.station_id))
    for (const [id, entry] of markerEntities) {
      if (!currentIds.has(id)) {
        viewer.entities.remove(entry.entity)
        markerEntities.delete(id)
      }
    }

    if (!visible) {
      for (const entry of markerEntities.values()) {
        entry.entity.show = false
      }
      viewer.scene.requestRender()
      return
    }

    for (const sensor of sensors) {
      if (sensor.latitude == null || sensor.longitude == null) continue

      const existing = markerEntities.get(sensor.station_id)
      const color = _tempToColor(sensor.temperature)

      if (existing) {
        existing.entity.show = true
        existing.entity.position = Cesium.Cartesian3.fromDegrees(sensor.longitude, sensor.latitude, 20)
        existing.entity.point.color = color
        existing.sensorData = sensor
      } else {
        const entity = viewer.entities.add({
          position: Cesium.Cartesian3.fromDegrees(sensor.longitude, sensor.latitude, 20),
          point: {
            pixelSize: 14,
            color,
            outlineColor: Cesium.Color.WHITE,
            outlineWidth: 2,
            heightReference: Cesium.HeightReference.RELATIVE_TO_GROUND,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
        })
        markerEntities.set(sensor.station_id, { entity, sensorData: sensor })
      }
    }

    viewer.scene.requestRender()
  }

  /**
   * Register a click handler that detects clicks on sensor marker entities.
   */
  function setupClickHandler() {
    const viewer = getViewer()
    if (!viewer) return

    // Suppress Cesium's default infoBox for all entities
    viewer.selectedEntityChanged.addEventListener(() => {
      viewer.selectedEntity = undefined
    })

    clickHandler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)

    clickHandler.setInputAction((click) => {
      if (getIsDrawing()) return

      const picked = viewer.scene.pick(click.position)
      if (!Cesium.defined(picked) || !picked.id) return

      // Check if the picked entity is one of our sensor markers
      for (const [, entry] of markerEntities) {
        if (entry.entity === picked.id) {
          emit('sensor-click', {
            sensor: entry.sensorData,
            screenX: click.position.x,
            screenY: click.position.y,
          })
          return
        }
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK)
  }

  /** Remove all markers and the click handler. */
  function cleanup() {
    const viewer = getViewer()
    if (viewer) {
      for (const entry of markerEntities.values()) {
        viewer.entities.remove(entry.entity)
      }
    }
    markerEntities.clear()

    if (clickHandler) {
      clickHandler.destroy()
      clickHandler = null
    }
  }

  return { updateMarkers, setupClickHandler, cleanup }
}


// ── Helpers ────────────────────────────────────────────────────────────────

/**
 * Map a temperature value to a color on a blue→green→yellow→red gradient.
 * Range: -5°C (cold blue) → 15°C (neutral green) → 35°C (hot red)
 */
function _tempToColor(temp) {
  if (temp == null) return Cesium.Color.GRAY

  const t = Math.max(-5, Math.min(40, temp))
  const ratio = (t + 5) / 45 // 0..1

  if (ratio < 0.33) {
    const f = ratio / 0.33
    return new Cesium.Color(0, f, 1 - f, 1)
  } else if (ratio < 0.66) {
    const f = (ratio - 0.33) / 0.33
    return new Cesium.Color(f, 1, 0, 1)
  } else {
    const f = (ratio - 0.66) / 0.34
    return new Cesium.Color(1, 1 - f, 0, 1)
  }
}
