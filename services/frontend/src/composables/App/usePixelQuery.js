import { ref } from 'vue'
import { predictionApi } from '../../services/predictionApi.js'

/**
 * usePixelQuery — Fetches layer values for the map point the user clicked on.
 *
 * When the user clicks on the Cesium map (outside of a workflow or download session),
 * CesiumViewer emits a 'pixel-click' event with geographic coordinates.
 * This composable handles that event: it shows a loading state, calls the prediction
 * service, and exposes the result to the PixelInfoPanel component.
 *
 * @param {Object}    options
 * @param {Function}  options.isBlocked - Returns true when the click should be ignored
 *                      (e.g. during an active workflow or download drawing session)
 */
export function usePixelQuery({ isBlocked }) {

  const showPixelInfo = ref(false)
  const pixelData     = ref(null)
  const pixelLoading  = ref(false)
  const pixelScreenX  = ref(0)
  const pixelScreenY  = ref(0)

  /**
   * Handle a 'pixel-click' event emitted by CesiumViewer.
   * Positions the PixelInfoPanel near the click and fetches all layer values.
   *
   * @param {{ lon, lat, screenX, screenY }} param0
   */
  async function onPixelClick({ lon, lat, screenX, screenY }) {
    if (isBlocked()) return

    pixelScreenX.value  = screenX
    pixelScreenY.value  = screenY
    showPixelInfo.value = true
    pixelLoading.value  = true
    // Show coordinates immediately while the request is in flight
    pixelData.value     = { lon, lat, values: {} }

    try {
      pixelData.value = await predictionApi.getPixelValue(lon, lat)
    } catch (err) {
      console.error('Pixel value fetch failed:', err)
      // Keep showing coordinates even on error so the panel doesn't disappear
      pixelData.value = { lon, lat, values: {} }
    } finally {
      pixelLoading.value = false
    }
  }

  return { showPixelInfo, pixelData, pixelLoading, pixelScreenX, pixelScreenY, onPixelClick }
}
