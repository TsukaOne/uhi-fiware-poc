import { ref } from 'vue'
import { predictionApi } from '../../services/predictionApi.js'

/**
 * useLayerInfo — Manages the 2-step layer statistics modal.
 *
 * Step 1 — Region choice modal: the user picks Full Map, Bounding Box, or Polygon.
 * Step 2 — Results modal: shows mean/min/max/std/pixel_count for the selected region.
 *
 * When the user picks Bounding Box or Polygon, this composable activates drawing mode.
 * Once the geometry is drawn, `onInfoGeometryDrawn` must be called by the parent router.
 *
 * @param {Object}   options
 * @param {Function} options.getLayers              - Returns the layers array
 * @param {Function} options.startDrawingBoundingBox - Activates bbox drawing mode
 * @param {Function} options.startDrawingPolygon     - Activates polygon drawing mode
 * @param {Function} options.addGeometry             - Registers drawn geometry
 * @param {Function} options.stopDrawing             - Clears drawing mode
 */
export function useLayerInfo({
  getLayers,
  startDrawingBoundingBox,
  startDrawingPolygon,
  addGeometry,
  stopDrawing,
}) {

  // ── Step 1: region choice ───────────────────────────────────────────────────
  const showLayerInfoChoice = ref(false)
  const layerInfoName       = ref(null)   // display name of the target layer
  const layerInfoLayerId    = ref(null)   // internal ID of the target layer

  // ── Step 2: statistics results ──────────────────────────────────────────────
  const showLayerInfoResults = ref(false)
  const layerInfoLoading     = ref(false)
  const layerInfoError       = ref(null)
  const layerInfoStats       = ref(null)
  const layerInfoRegionLabel = ref('Full raster')

  /**
   * True while waiting for the user to finish drawing a region for stats.
   * Exposed so the parent router knows to send drawn geometry here.
   */
  const infoMode = ref(false)


  // ── Public API ──────────────────────────────────────────────────────────────

  /**
   * Open the region choice modal for a given layer.
   * Called when the user clicks the "statistics" icon in LayerControls.
   */
  function onLayerMetadata(layerId) {
    const layer = getLayers().find(l => l.id === layerId)
    layerInfoName.value    = layer ? layer.name : layerId
    layerInfoLayerId.value = layerId
    layerInfoStats.value   = null
    layerInfoError.value   = null
    showLayerInfoChoice.value = true
  }

  /**
   * Handle the user's region choice from the modal.
   * 'fullMap' triggers an immediate fetch; 'polygon'/'boundingBox' start drawing mode.
   */
  function onInfoChoice(choice) {
    showLayerInfoChoice.value = false

    if (choice === 'fullMap') {
      layerInfoRegionLabel.value = 'Full raster'
      fetchLayerStats(null)
    } else if (choice === 'boundingBox') {
      infoMode.value = true
      startDrawingBoundingBox()
    } else if (choice === 'polygon') {
      infoMode.value = true
      startDrawingPolygon()
    }
  }

  /**
   * Called by the parent's geometry router once the user finishes drawing.
   * Only called when infoMode is true.
   */
  function onInfoGeometryDrawn(geometry) {
    addGeometry(geometry)
    stopDrawing()
    infoMode.value = false
    layerInfoRegionLabel.value = 'Selected zone'
    fetchLayerStats(geometry.geoJSON)
  }

  function closeLayerInfoResults() {
    showLayerInfoResults.value = false
  }


  // ── Private ─────────────────────────────────────────────────────────────────

  async function fetchLayerStats(geometry) {
    layerInfoLoading.value     = true
    layerInfoStats.value       = null
    layerInfoError.value       = null
    showLayerInfoResults.value = true

    try {
      layerInfoStats.value = await predictionApi.getLayerStats(layerInfoLayerId.value, geometry)
    } catch (err) {
      console.error('Layer stats fetch failed:', err)
      layerInfoError.value = err.message || 'Failed to load layer statistics'
    } finally {
      layerInfoLoading.value = false
    }
  }

  return {
    showLayerInfoChoice,
    showLayerInfoResults,
    layerInfoLoading,
    layerInfoError,
    layerInfoStats,
    layerInfoName,
    layerInfoRegionLabel,
    infoMode,
    onLayerMetadata,
    onInfoChoice,
    onInfoGeometryDrawn,
    closeLayerInfoResults,
  }
}
