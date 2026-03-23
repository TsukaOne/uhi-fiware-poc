import { ref, computed } from 'vue'
import { predictionApi } from '../../services/predictionApi.js'

/**
 * useDownload — Manages the GeoTIFF download flow for a WMS layer.
 *
 * Two modes:
 *  - Full map: confirmed immediately via a dialog, no drawing required.
 *  - Bounding box crop: activates drawing mode; once the geometry is drawn,
 *    `onDownloadGeometryDrawn` must be called by the parent router.
 *
 * @param {Object}   options
 * @param {Function} options.getLayers              - Returns the layers array (for display names)
 * @param {Function} options.startDrawingBoundingBox - Activates bbox drawing mode
 * @param {Function} options.addGeometry             - Registers drawn geometry
 * @param {Function} options.stopDrawing             - Clears drawing mode
 */
export function useDownload({
  getLayers,
  startDrawingBoundingBox,
  addGeometry,
  stopDrawing,
}) {

  // ── Download modal (layer selection entry point) ────────────────────────────
  const showToolModal    = ref(false)
  const toolModalType    = ref('download')
  const toolModalLayerId = ref(null)

  const toolModalLayerName = computed(() => {
    if (!toolModalLayerId.value) return null
    const layer = getLayers().find(l => l.id === toolModalLayerId.value)
    return layer ? layer.name : toolModalLayerId.value
  })

  // ── Confirm dialog ──────────────────────────────────────────────────────────
  const showDownloadConfirm  = ref(false)
  const downloadConfirmText  = ref('')
  const pendingDownloadGeometry = ref(null) // null = full map

  // ── Download execution ──────────────────────────────────────────────────────
  const isDownloading      = ref(false)
  const activeDownloadLayer = ref(null)

  /**
   * True while the user is drawing a bounding box to crop the download.
   * Exposed so the parent router knows to forward drawn geometry here.
   */
  const downloadMode = ref(false)


  // ── Public API ──────────────────────────────────────────────────────────────

  /**
   * Open the download mode choice modal for a given layer.
   * Called when the user clicks the download icon in LayerControls.
   */
  function onLayerDownload(layerId) {
    toolModalType.value    = 'download'
    toolModalLayerId.value = layerId
    showToolModal.value    = true
  }

  function closeToolModal() {
    showToolModal.value    = false
    toolModalLayerId.value = null
  }

  /**
   * Handle the user's choice from the download modal:
   *  - 'fullMap'     → show confirm dialog immediately
   *  - 'boundingBox' → start drawing, wait for geometry
   */
  function onToolModalChoice(choice) {
    const layerId = toolModalLayerId.value
    closeToolModal()
    activeDownloadLayer.value = layerId

    if (choice === 'fullMap') {
      pendingDownloadGeometry.value = null
      const layer = getLayers().find(l => l.id === layerId)
      const name  = layer ? layer.name : layerId
      downloadConfirmText.value  = `Download the full ${name} layer as GeoTIFF?`
      showDownloadConfirm.value  = true
    } else {
      // boundingBox: activate drawing, wait for parent router to call onDownloadGeometryDrawn
      downloadMode.value = true
      startDrawingBoundingBox()
    }
  }

  /**
   * Called by the parent's geometry router once the crop box is drawn.
   * Only called when downloadMode is true.
   */
  function onDownloadGeometryDrawn(geometry) {
    addGeometry(geometry)
    stopDrawing()
    downloadMode.value = false
    pendingDownloadGeometry.value = geometry.geoJSON
    const layer = getLayers().find(l => l.id === activeDownloadLayer.value)
    const name  = layer ? layer.name : (activeDownloadLayer.value || 'layer')
    downloadConfirmText.value = `Download the selected ${name} zone as GeoTIFF?`
    showDownloadConfirm.value = true
  }

  /**
   * Execute the actual download after the user confirms.
   * Builds the filename, POSTs to the backend, triggers a browser file save.
   */
  async function executeDownload() {
    showDownloadConfirm.value = false
    isDownloading.value = true

    const geometry = pendingDownloadGeometry.value
    const layerId  = activeDownloadLayer.value || 'uhi'
    // fileName built from layerId directly — toBackendLayer is now inside predictionApi
    const fileName = geometry ? `${layerId}_crop.tif` : `${layerId}_full.tif`

    try {
      const blob = await predictionApi.downloadLayer(layerId, geometry)

      // Trigger browser file-save dialog
      const url = URL.createObjectURL(blob)
      const a   = document.createElement('a')
      a.href     = url
      a.download = fileName
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Download failed:', err)
    } finally {
      isDownloading.value       = false
      pendingDownloadGeometry.value = null
      activeDownloadLayer.value = null
    }
  }

  return {
    showToolModal,
    toolModalType,
    toolModalLayerId,
    toolModalLayerName,
    showDownloadConfirm,
    downloadConfirmText,
    isDownloading,
    downloadMode,
    onLayerDownload,
    closeToolModal,
    onToolModalChoice,
    onDownloadGeometryDrawn,
    executeDownload,
  }
}
