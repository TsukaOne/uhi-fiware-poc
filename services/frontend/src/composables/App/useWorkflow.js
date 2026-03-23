import { ref } from 'vue'

/**
 * useWorkflow — Manages the 3-step prediction workflow state machine.
 *
 * The workflow is triggered after the user draws a zone on the map:
 *   Step 1 — Zone selected → show ZoneObjectsPanel (drag & drop) + ZoneInfoPanel
 *   Step 2 — User confirms → show PredictionPanel
 *   Step 3 — Prediction complete → overlay result on map, save to history
 *
 * Cancellation resets all state to step 0 (idle).
 *
 * @param {Object}   options
 * @param {Function} options.addGeometry  - Adds geometry to the global drawn geometries list
 * @param {Function} options.stopDrawing  - Clears the active drawing mode
 * @param {Function} options.set3D        - Switches the viewer to 3D mode
 * @param {Function} options.getViewMode  - Returns the current view mode string ('2D' | '3D')
 */
export function useWorkflow({ addGeometry, stopDrawing, set3D, getViewMode }) {

  // ── Workflow state ──────────────────────────────────────────────────────────
  const activeGeometry      = ref(null)   // geometry produced by the drawing tool
  const showSelectionOverlay = ref(false) // SVG cutout overlay on top of the map
  const showWorkflowBar      = ref(false) // bottom progress bar (steps 1→2→3)
  const showPredictionPanel  = ref(false) // right-side panel for running predictions
  const workflowStep         = ref(0)     // 0=idle, 1=objects, 2=predict, 3=done
  const showZoneObjectsPanel = ref(false) // left-side panel for placing 3D objects
  const showZoneInfoPanel    = ref(false) // right-side panel showing zone statistics
  const zoneObjects          = ref([])    // list of 3D objects placed by the user
  const predictionOverlay    = ref(null)  // { image_base64, bounds, stats } for Cesium
  const zoneStatsData        = ref(null)  // stats forwarded from ZoneInfoPanel to PredictionPanel
  const predictionHistory    = ref([])    // ephemeral in-memory run history


  // ── Step transitions ────────────────────────────────────────────────────────

  /**
   * Called when the user finishes drawing a zone.
   * Transitions from STEP 0 -->  1 (place objects).
   */
  function onGeometryDrawnPredict(geometry) {
    addGeometry(geometry)
    stopDrawing()
    activeGeometry.value      = geometry
    showSelectionOverlay.value = true
    showWorkflowBar.value      = true
    workflowStep.value         = 1
    showZoneObjectsPanel.value = true
    showZoneInfoPanel.value    = true
    showPredictionPanel.value  = false
    // 3D gives a better spatial overview of the selected zone
    if (getViewMode() !== '3D') set3D()
  }

  /**
   * Navigate to a numbered step via the workflow bar.
   * Only steps 1 and 2 are navigable (step 3 is set automatically after prediction).
   */
  function goToStep(step) {
    if (step === 1) backToObjects()
    else if (step === 2) goToPredict()
  }

  /** Step 1 → Step 2: open the prediction panel, hide the zone info panel */
  function goToPredict() {
    workflowStep.value        = 2
    showPredictionPanel.value = true
    showZoneInfoPanel.value   = false
  }

  /** Step 2 → Step 1: back button — hide prediction panel, show zone info */
  function backToObjects() {
    workflowStep.value        = 1
    showPredictionPanel.value = false
    showZoneInfoPanel.value   = true
  }

  /** Called when the prediction panel emits 'close' */
  function closePredictionPanel() {
    showPredictionPanel.value = false
    workflowStep.value        = 1
    showZoneInfoPanel.value   = true
  }

  /** Cancel button — reset all workflow state to idle */
  function cancelWorkflow() {
    showSelectionOverlay.value = false
    showWorkflowBar.value      = false
    showPredictionPanel.value  = false
    showZoneObjectsPanel.value = false
    showZoneInfoPanel.value    = false
    workflowStep.value         = 0
    activeGeometry.value       = null
    zoneObjects.value          = []
    predictionOverlay.value    = null
    zoneStatsData.value        = null
  }

  // ── Event handlers from child panels ───────────────────────────────────────

  /** Receives the updated objects list from ZoneObjectsPanel */
  function onZoneObjectsChanged(objects) {
    zoneObjects.value = objects
  }

  /**
   * Receives the prediction result from PredictionPanel.
   * Advances to step 3 and saves an entry to the run history.
   *
   * @param {{ result: { image_base64, bounds, stats } }} payload
   */
  function onPredict(payload) {
    if (!payload.result) return

    predictionOverlay.value = {
      image_base64: payload.result.image_base64,
      bounds:       payload.result.bounds,
      stats:        payload.result.stats,
    }
    workflowStep.value = 3

    predictionHistory.value.unshift({
      id:          Date.now(),
      date:        new Date().toLocaleString(),
      stats:       payload.result.stats,
      objectCount: zoneObjects.value.length,
    })
  }

  return {
    activeGeometry,
    showSelectionOverlay,
    showWorkflowBar,
    showPredictionPanel,
    workflowStep,
    showZoneObjectsPanel,
    showZoneInfoPanel,
    zoneObjects,
    predictionOverlay,
    zoneStatsData,
    predictionHistory,
    onGeometryDrawnPredict,
    goToStep,
    goToPredict,
    backToObjects,
    closePredictionPanel,
    cancelWorkflow,
    onZoneObjectsChanged,
    onPredict,
  }
}
