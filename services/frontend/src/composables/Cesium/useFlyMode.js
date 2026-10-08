import * as Cesium from 'cesium'

/**
 * useFlyMode — Free-flight camera over the city, no gravity, no collisions.
 *
 * Arrow keys move, the mouse steers. The cursor stays visible: it only steers
 * once it leaves a dead zone around the screen centre, so the user can still
 * reach the side panels without the camera drifting.
 *
 * Rather than chaining camera.lookRight()/lookUp() — which accumulates roll
 * drift over time — we keep heading/pitch ourselves and rebuild the view every
 * frame with roll forced to 0. That also makes clamping the pitch trivial.
 */

// Steering: normalized cursor offset from centre, below which nothing happens
const DEAD_ZONE = 0.12

// Maximum turn rates, in radians per second, reached at the screen edge
const MAX_YAW_RATE   = 1.2
const MAX_PITCH_RATE = 0.8

// Looking straight up or down makes the heading ambiguous — stop short of it
const MAX_PITCH = Cesium.Math.toRadians(85)

// Cruise speed scales with altitude so flying at 100 m and at 5 km feel alike
const SPEED_PER_METER = 0.25
const MIN_SPEED       = 40      // m/s
const MAX_SPEED       = 3000    // m/s
const BOOST_FACTOR    = 4

// Wheel adjusts a persistent multiplier on top of the altitude-derived speed
const MIN_SPEED_MULTIPLIER = 0.25
const MAX_SPEED_MULTIPLIER = 8
const WHEEL_STEP           = 1.15

// Never let the camera sink below this height above the ellipsoid
const MIN_ALTITUDE = 5

// A backgrounded tab can hand us a multi-second delta; cap it so the camera
// does not teleport when the user comes back
const MAX_FRAME_DELTA = 0.1

/**
 * @param {Object} options
 * @param {() => Cesium.Viewer} options.getViewer    - Returns the current Cesium viewer
 * @param {() => boolean}       options.getIsDrawing - Whether a drawing session owns the keyboard
 * @param {Function}            [options.onExit]     - Called when the user presses Escape
 */
export function useFlyMode({ getViewer, getIsDrawing, onExit }) {

  // ── Internal state ──────────────────────────────────────────────────────────

  let active = false

  /** Camera orientation we own while flying */
  let heading = 0
  let pitch = 0

  /** Currently held keys, by KeyboardEvent.code (layout independent) */
  const heldKeys = new Set()

  /** Normalized cursor offset from the canvas centre, each component in [-1, 1] */
  let steerX = 0
  let steerY = 0

  let speedMultiplier = 1
  let lastFrameTime = 0
  let currentSpeed = 0

  /** Viewer settings captured on enable(), restored on disable() */
  let savedSettings = null

  /** Listener handles, so disable() can unwind exactly what enable() installed */
  let removePreRender = null
  let canvasListeners = []
  let windowListeners = []

  // Scratch vectors — reused every frame to avoid allocating in the render loop
  const scratchForward = new Cesium.Cartesian3()
  const scratchRight = new Cesium.Cartesian3()
  const scratchUp = new Cesium.Cartesian3()
  const scratchMove = new Cesium.Cartesian3()
  const scratchPosition = new Cesium.Cartesian3()


  // ── Public API ──────────────────────────────────────────────────────────────

  /**
   * Enter free-flight mode. Idempotent.
   */
  function enable() {
    const viewer = getViewer()
    if (!viewer || active) return

    active = true

    const scene = viewer.scene
    const controller = scene.screenSpaceCameraController

    savedSettings = {
      requestRenderMode:       scene.requestRenderMode,
      enableRotate:            controller.enableRotate,
      enableTilt:              controller.enableTilt,
      enableTranslate:         controller.enableTranslate,
      enableLook:              controller.enableLook,
      enableZoom:              controller.enableZoom,
      enableCollisionDetection: controller.enableCollisionDetection,
    }

    // The viewer renders on demand; free flight needs a continuous loop
    scene.requestRenderMode = false

    // We drive the camera ourselves — hand no input back to Cesium
    controller.enableRotate = false
    controller.enableTilt = false
    controller.enableTranslate = false
    controller.enableLook = false
    controller.enableZoom = false

    // This is what makes it "no gravity": the camera passes through terrain
    // and buildings instead of being pushed back above them.
    controller.enableCollisionDetection = false

    // A flyTo may still be animating (3D mode kicks one off); it would fight
    // our per-frame setView.
    viewer.camera.cancelFlight()

    // Adopt the camera's current orientation so entering fly mode does not jump
    heading = viewer.camera.heading
    pitch = Cesium.Math.clamp(viewer.camera.pitch, -MAX_PITCH, MAX_PITCH)

    steerX = 0
    steerY = 0
    speedMultiplier = 1
    currentSpeed = 0
    heldKeys.clear()
    lastFrameTime = performance.now()

    _installListeners(viewer)

    removePreRender = scene.preRender.addEventListener(_onPreRender)
  }

  /**
   * Leave free-flight mode and give the camera back to Cesium. Idempotent.
   */
  function disable() {
    const viewer = getViewer()
    if (!active) return

    active = false
    heldKeys.clear()
    steerX = 0
    steerY = 0

    _removeListeners()

    if (removePreRender) {
      removePreRender()
      removePreRender = null
    }

    if (viewer && !viewer.isDestroyed() && savedSettings) {
      const scene = viewer.scene
      const controller = scene.screenSpaceCameraController

      controller.enableRotate = savedSettings.enableRotate
      controller.enableTilt = savedSettings.enableTilt
      controller.enableTranslate = savedSettings.enableTranslate
      controller.enableLook = savedSettings.enableLook
      controller.enableZoom = savedSettings.enableZoom
      controller.enableCollisionDetection = savedSettings.enableCollisionDetection
      scene.requestRenderMode = savedSettings.requestRenderMode

      // Leave the camera level so the restored controls behave predictably
      viewer.camera.setView({
        orientation: { heading, pitch, roll: 0 }
      })
      scene.requestRender()
    }

    savedSettings = null
  }

  function isActive() {
    return active
  }

  /**
   * Live figures for the HUD.
   * @returns {{altitude: number, speed: number, heading: number}}
   */
  function getTelemetry() {
    const viewer = getViewer()
    if (!viewer || viewer.isDestroyed()) {
      return { altitude: 0, speed: 0, heading: 0 }
    }
    return {
      altitude: viewer.camera.positionCartographic.height,
      speed: currentSpeed,
      heading: Cesium.Math.toDegrees(heading),
    }
  }


  // ── Frame loop ──────────────────────────────────────────────────────────────

  function _onPreRender() {
    const viewer = getViewer()
    if (!active || !viewer || viewer.isDestroyed()) return

    const now = performance.now()
    const dt = Math.min((now - lastFrameTime) / 1000, MAX_FRAME_DELTA)
    lastFrameTime = now

    if (dt <= 0) return

    const camera = viewer.camera

    // ── Steering ──
    heading = _wrapAngle(heading + _steerRate(steerX, MAX_YAW_RATE) * dt)
    pitch = Cesium.Math.clamp(
      pitch - _steerRate(steerY, MAX_PITCH_RATE) * dt,
      -MAX_PITCH,
      MAX_PITCH
    )

    // ── Speed ──
    const altitude = camera.positionCartographic.height
    const baseSpeed = Cesium.Math.clamp(altitude * SPEED_PER_METER, MIN_SPEED, MAX_SPEED)
    const boost = heldKeys.has('ShiftLeft') || heldKeys.has('ShiftRight') ? BOOST_FACTOR : 1
    const speed = baseSpeed * speedMultiplier * boost

    // ── Translation ──
    // Forward follows the view direction (pitch included) so the camera dives
    // where it looks. Up/down use the true local vertical instead, so Space and
    // Ctrl always climb and descend regardless of where the camera points.
    Cesium.Cartesian3.normalize(camera.direction, scratchForward)
    Cesium.Cartesian3.normalize(camera.right, scratchRight)
    Cesium.Cartesian3.normalize(camera.positionWC, scratchUp)

    Cesium.Cartesian3.clone(Cesium.Cartesian3.ZERO, scratchMove)

    if (heldKeys.has('ArrowUp'))    _addScaled(scratchForward, 1)
    if (heldKeys.has('ArrowDown'))  _addScaled(scratchForward, -1)
    if (heldKeys.has('ArrowRight')) _addScaled(scratchRight, 1)
    if (heldKeys.has('ArrowLeft'))  _addScaled(scratchRight, -1)
    if (heldKeys.has('Space'))      _addScaled(scratchUp, 1)
    if (heldKeys.has('ControlLeft') || heldKeys.has('ControlRight')) _addScaled(scratchUp, -1)

    const moveLength = Cesium.Cartesian3.magnitude(scratchMove)
    currentSpeed = moveLength > 0 ? speed : 0

    Cesium.Cartesian3.clone(camera.position, scratchPosition)

    if (moveLength > 0) {
      // Normalize so diagonals are not faster than straight lines
      Cesium.Cartesian3.multiplyByScalar(scratchMove, speed * dt / moveLength, scratchMove)
      Cesium.Cartesian3.add(scratchPosition, scratchMove, scratchPosition)
      _clampAltitude(scratchPosition)
    }

    camera.setView({
      destination: scratchPosition,
      orientation: { heading, pitch, roll: 0 }
    })
  }

  /** Accumulate `axis * sign` into the scratch move vector. */
  function _addScaled(axis, sign) {
    scratchMove.x += axis.x * sign
    scratchMove.y += axis.y * sign
    scratchMove.z += axis.z * sign
  }

  /**
   * Map a normalized cursor offset onto a turn rate.
   * Quadratic past the dead zone: fine control near the centre, responsive at
   * the edges.
   */
  function _steerRate(offset, maxRate) {
    const magnitude = Math.abs(offset)
    if (magnitude <= DEAD_ZONE) return 0
    const normalized = (magnitude - DEAD_ZONE) / (1 - DEAD_ZONE)
    return Math.sign(offset) * normalized * normalized * maxRate
  }

  /** Keep the camera above the ellipsoid surface. Mutates `position`. */
  function _clampAltitude(position) {
    const carto = Cesium.Cartographic.fromCartesian(position)
    if (!carto || carto.height >= MIN_ALTITUDE) return
    Cesium.Cartesian3.fromRadians(carto.longitude, carto.latitude, MIN_ALTITUDE, undefined, position)
  }

  function _wrapAngle(angle) {
    const twoPi = Cesium.Math.TWO_PI
    return ((angle % twoPi) + twoPi) % twoPi
  }


  // ── Input listeners ─────────────────────────────────────────────────────────

  function _installListeners(viewer) {
    const canvas = viewer.scene.canvas

    const onMouseMove = (event) => {
      const rect = canvas.getBoundingClientRect()
      if (!rect.width || !rect.height) return
      // -1 at the left/top edge, +1 at the right/bottom edge, 0 at the centre
      steerX = ((event.clientX - rect.left) / rect.width) * 2 - 1
      steerY = ((event.clientY - rect.top) / rect.height) * 2 - 1
    }

    const onMouseLeave = () => {
      steerX = 0
      steerY = 0
    }

    const onWheel = (event) => {
      event.preventDefault()
      const factor = event.deltaY < 0 ? WHEEL_STEP : 1 / WHEEL_STEP
      speedMultiplier = Cesium.Math.clamp(
        speedMultiplier * factor,
        MIN_SPEED_MULTIPLIER,
        MAX_SPEED_MULTIPLIER
      )
    }

    const onKeyDown = (event) => {
      if (_keyboardIsBusy()) return

      if (event.code === 'Escape') {
        event.preventDefault()
        if (onExit) onExit()
        return
      }

      if (!_isFlightKey(event.code)) return
      event.preventDefault()   // arrows and Space would otherwise scroll the page
      heldKeys.add(event.code)
    }

    const onKeyUp = (event) => {
      heldKeys.delete(event.code)
    }

    // Alt-tabbing away swallows the keyup, leaving a key stuck down
    const onBlur = () => heldKeys.clear()

    canvasListeners = [
      ['mousemove', onMouseMove, undefined],
      ['mouseleave', onMouseLeave, undefined],
      ['wheel', onWheel, { passive: false }],
    ]
    canvasListeners.forEach(([type, handler, opts]) => canvas.addEventListener(type, handler, opts))

    windowListeners = [
      ['keydown', onKeyDown],
      ['keyup', onKeyUp],
      ['blur', onBlur],
    ]
    windowListeners.forEach(([type, handler]) => window.addEventListener(type, handler))

    // Remember the canvas so _removeListeners does not depend on viewer state
    canvasListeners.canvas = canvas
  }

  function _removeListeners() {
    const canvas = canvasListeners.canvas
    if (canvas) {
      canvasListeners.forEach(([type, handler, opts]) => canvas.removeEventListener(type, handler, opts))
    }
    canvasListeners = []

    windowListeners.forEach(([type, handler]) => window.removeEventListener(type, handler))
    windowListeners = []
  }

  function _isFlightKey(code) {
    return code === 'ArrowUp' || code === 'ArrowDown' ||
           code === 'ArrowLeft' || code === 'ArrowRight' ||
           code === 'Space' ||
           code === 'ControlLeft' || code === 'ControlRight' ||
           code === 'ShiftLeft' || code === 'ShiftRight'
  }

  /**
   * True when something else legitimately owns the keyboard: an active drawing
   * session (which binds Escape and Ctrl+Z) or a focused text field such as the
   * geocoder — typing there must not launch the camera.
   */
  function _keyboardIsBusy() {
    if (getIsDrawing && getIsDrawing()) return true

    const el = document.activeElement
    if (!el) return false

    const tag = el.tagName
    return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable
  }


  return { enable, disable, isActive, getTelemetry }
}
