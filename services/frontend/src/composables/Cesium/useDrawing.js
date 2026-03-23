import * as Cesium from 'cesium'

/**
 * useDrawing — Manages polygon and bounding-box drawing on the Cesium canvas.
 *
 * Responsibilities:
 *  - Track drawn points and their visual entities
 *  - Handle mouse events (click, move, right-click) and keyboard shortcuts
 *  - Build the final geometry object and emit it to the parent
 *
 * @param {Object} options
 * @param {() => Cesium.Viewer} options.getViewer - Returns the current Cesium viewer instance
 * @param {Function} options.emit - Vue emit function for 'geometry-drawn' and 'drawing-active'
 */
export function useDrawing({ getViewer, emit }) {

  // ── Internal state 
  //  ──
  let drawingMode = null          // 'polygon' | 'boundingBox' | null
  let isDrawing = false           // True while a drawing session is active
  let drawnPoints = []            // Array of { longitude, latitude, cartesian }
  let pointEntities = []          // Visual dot entities on the map
  let previewEntity = null        // Live preview shape following the cursor
  let currentMousePosition = null // Last known mouse screen position
  let mouseHandler = null         // Cesium ScreenSpaceEventHandler
  let drawingKeyHandler = null    // DOM keydown listener reference


  /**
   * Start drawing mode for the given geometry type & Sets up mouse and keyboard handlers on the Cesium canvas.
   */
  function startDrawing(mode) {
    const viewer = getViewer()
    if (!viewer) return

    drawingMode = mode
    drawnPoints = []
    isDrawing = true

    emit('drawing-active', true)

    if (!mouseHandler) {
      mouseHandler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas)
    }

    // Left-click: add a point to the drawing
    mouseHandler.setInputAction((click) => {
      if (!isDrawing || !drawingMode) return

      const cartesian = _pickPosition(viewer, click.position)
      if (!cartesian) return

      const cartographic = Cesium.Cartographic.fromCartesian(cartesian)
      const lon = Cesium.Math.toDegrees(cartographic.longitude)
      const lat = Cesium.Math.toDegrees(cartographic.latitude)

      // Snap to terrain surface to avoid floating points
      const snappedCartesian = Cesium.Cartesian3.fromDegrees(lon, lat, cartographic.height)
      drawnPoints.push({ longitude: lon, latitude: lat, cartesian: snappedCartesian })

      // Visual feedback: green dot at each placed point
      const pointEntity = viewer.entities.add({
        position: snappedCartesian,
        point: {
          pixelSize: 8,
          color: Cesium.Color.GREEN,
          outlineColor: Cesium.Color.WHITE,
          outlineWidth: 2,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        }
      })
      pointEntities.push(pointEntity)
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK)

    // Mouse move: update the live preview shape
    mouseHandler.setInputAction((move) => {
      if (!isDrawing || !drawingMode) return
      currentMousePosition = move.endPosition
      _updatePreview(viewer, move.endPosition)
    }, Cesium.ScreenSpaceEventType.MOUSE_MOVE)

    // Right-click: finish drawing
    mouseHandler.setInputAction(() => {
      if (!isDrawing || !drawingMode) return
      _finishDrawing(viewer)
    }, Cesium.ScreenSpaceEventType.RIGHT_CLICK)

    // Keyboard: Ctrl+Z = undo last point, Escape = cancel
    drawingKeyHandler = function onKeyDown(e) {
      if (!isDrawing) return
      if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
        e.preventDefault()
        undoLastPoint()
      }
      if (e.key === 'Escape') {
        e.preventDefault()
        stopDrawing()
        emit('drawing-active', false)
      }
    }
    document.addEventListener('keydown', drawingKeyHandler)
  }

  /**
   * Remove the last placed point and refresh the preview.
   */
  function undoLastPoint() {
    const viewer = getViewer()
    if (!isDrawing || drawnPoints.length === 0 || !viewer) return

    drawnPoints.pop()
    const lastEntity = pointEntities.pop()
    if (lastEntity) viewer.entities.remove(lastEntity)

    // Rebuild preview without the removed point
    if (previewEntity) {
      viewer.entities.remove(previewEntity)
      previewEntity = null
    }
    if (currentMousePosition) {
      _updatePreview(viewer, currentMousePosition)
    }
    viewer.scene.requestRender()
  }

  /**
   * Cancel drawing and clean up all entities and handlers.
   */
  function stopDrawing() {
    const viewer = getViewer()

    isDrawing = false
    drawingMode = null
    drawnPoints = []

    if (viewer) {
      pointEntities.forEach(e => viewer.entities.remove(e))
      if (previewEntity) {
        viewer.entities.remove(previewEntity)
        previewEntity = null
      }
    }
    pointEntities = []

    if (mouseHandler) {
      mouseHandler.removeInputAction(Cesium.ScreenSpaceEventType.LEFT_CLICK)
      mouseHandler.removeInputAction(Cesium.ScreenSpaceEventType.RIGHT_CLICK)
      mouseHandler.destroy()
      mouseHandler = null
    }

    if (drawingKeyHandler) {
      document.removeEventListener('keydown', drawingKeyHandler)
      drawingKeyHandler = null
    }
  }

  /** Returns true while a drawing session is active (used by pixel click guard). */
  function getIsDrawing() {
    return isDrawing
  }


  // ── Private helpers ─────────────────────────────────────────────────────────

  /**
   * Attempt to resolve a screen position to a world Cartesian3.
   * Tries: pickPosition → globe.pick (ray) → pickEllipsoid (fallback).
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

  /**
   * Update the live-preview entity that follows the cursor.
   * Shows a partial polygon outline or bounding box as the user draws.
   */
  function _updatePreview(viewer, mousePos) {
    if (!drawingMode || drawnPoints.length < 1) return

    const ray = viewer.camera.getPickRay(mousePos)
    const mouseCartesian = ray
      ? viewer.scene.globe.pick(ray, viewer.scene) ||
        viewer.camera.pickEllipsoid(mousePos, viewer.scene.globe.ellipsoid)
      : null

    if (!mouseCartesian) return

    if (previewEntity) {
      viewer.entities.remove(previewEntity)
      previewEntity = null
    }

    if (drawingMode === 'polygon' && drawnPoints.length >= 2) {
      // Show filled polygon with all placed points + cursor
      const positions = [...drawnPoints.map(p => p.cartesian), mouseCartesian]
      previewEntity = viewer.entities.add({
        polygon: {
          hierarchy: new Cesium.PolygonHierarchy(positions),
          material: Cesium.Color.GREEN.withAlpha(0.2),
          outline: true,
          outlineColor: Cesium.Color.LIME,
          outlineWidth: 2,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          classificationType: Cesium.ClassificationType.TERRAIN
        }
      })
    } else if (drawingMode === 'polygon' && drawnPoints.length === 1) {
      // Only one point placed yet: show a simple line to the cursor
      previewEntity = viewer.entities.add({
        polyline: {
          positions: [drawnPoints[0].cartesian, mouseCartesian],
          width: 2,
          material: Cesium.Color.LIME.withAlpha(0.8),
          clampToGround: true,
        }
      })
    } else if (drawingMode === 'boundingBox' && drawnPoints.length >= 1) {
      // Show the bounding box rectangle defined by first point and cursor
      const mouseCartographic = Cesium.Cartographic.fromCartesian(mouseCartesian)
      const mouseLon = Cesium.Math.toDegrees(mouseCartographic.longitude)
      const mouseLat = Cesium.Math.toDegrees(mouseCartographic.latitude)

      const minLat = Math.min(drawnPoints[0].latitude, mouseLat)
      const maxLat = Math.max(drawnPoints[0].latitude, mouseLat)
      const minLon = Math.min(drawnPoints[0].longitude, mouseLon)
      const maxLon = Math.max(drawnPoints[0].longitude, mouseLon)

      const boxCorners = [
        Cesium.Cartesian3.fromDegrees(minLon, minLat),
        Cesium.Cartesian3.fromDegrees(maxLon, minLat),
        Cesium.Cartesian3.fromDegrees(maxLon, maxLat),
        Cesium.Cartesian3.fromDegrees(minLon, maxLat)
      ]

      previewEntity = viewer.entities.add({
        polygon: {
          hierarchy: new Cesium.PolygonHierarchy(boxCorners),
          material: Cesium.Color.BLUE.withAlpha(0.2),
          outline: true,
          outlineColor: Cesium.Color.CYAN,
          outlineWidth: 2,
          heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          classificationType: Cesium.ClassificationType.TERRAIN,
        }
      })
    }
  }

  /**
   * Complete the drawing session: build the geometry object and emit it.
   * Requires at least 2 points; cancels silently otherwise.
   */
  function _finishDrawing(viewer) {
    if (drawnPoints.length < 2) {
      stopDrawing()
      return
    }

    if (previewEntity) {
      viewer.entities.remove(previewEntity)
      previewEntity = null
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
      geometry.summary = {
        type: 'Polygon',
        pointCount: drawnPoints.length,
        coordinates: drawnPoints.map(p => `(${p.latitude.toFixed(5)}, ${p.longitude.toFixed(5)})`)
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
      geometry.summary = {
        type: 'Bounding Box',
        bounds: `N:${maxLat.toFixed(5)} S:${minLat.toFixed(5)} E:${maxLon.toFixed(5)} W:${minLon.toFixed(5)}`
      }
    }

    console.log('→ Drawing finished:', geometry)
    emit('geometry-drawn', geometry)
    emit('drawing-active', false)

    stopDrawing()
  }

  return { startDrawing, stopDrawing, undoLastPoint, getIsDrawing }
}
