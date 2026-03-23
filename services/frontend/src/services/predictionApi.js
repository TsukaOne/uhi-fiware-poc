import { apiJSON, apiBlob } from './api.js'

const BASE = '/prediction'

/**
 * Frontend layer IDs → backend layer names expected by the prediction service.
 * Add mappings here when a new layer is added to the system.
 */
const BACKEND_LAYER_MAP = {
  'uhi_prediction': 'uhi',
}

function toBackendLayer(frontendId) {
  return BACKEND_LAYER_MAP[frontendId] || frontendId
}

/**
 * predictionApi — All endpoints of the prediction microservice.
 *
 * Base URL: /prediction  (proxied by Vite/nginx to http://localhost:8002)
 *
 * Usage:
 *   import { predictionApi } from '../services/predictionApi.js'
 *   const data = await predictionApi.getTBase()
 */
export const predictionApi = {

  /**
   * GET /vlinder/t_base
   * Fetch the current ambient temperature (T_base) from the VLINDER station network.
   * Returns: { value, station_name, station_id, fallback }
   */
  getTBase: () =>
    apiJSON(`${BASE}/vlinder/t_base`),

  /**
   * POST /predict/pixel/value
   * Fetch all layer values at a geographic point clicked on the map.
   *
   * @param {number} lon
   * @param {number} lat
   * @returns {{ lon, lat, values: Object }}
   */
  getPixelValue: (lon, lat) =>
    apiJSON(`${BASE}/predict/pixel/value`, {
      method: 'POST',
      body:   JSON.stringify({ lon, lat }),
    }),

  /**
   * POST /predict/layer/stats
   * Compute statistics (mean, min, max, std, pixel_count) for a WMS layer
   * over a given region. Pass geometry=null for full-map statistics.
   *
   * @param {string}      layerId  - Frontend layer ID (e.g. 'uhi_prediction', 'ndvi')
   * @param {Object|null} geometry - GeoJSON geometry, or null for full map
   */
  getLayerStats: (layerId, geometry) => {
    const body = { layer: toBackendLayer(layerId) }
    if (geometry) body.geometry = geometry
    return apiJSON(`${BASE}/predict/layer/stats`, {
      method: 'POST',
      body:   JSON.stringify(body),
    })
  },

  /**
   * POST /predict/zone/stats
   * Compute per-layer statistics for the entire selected zone.
   * Used by ZoneInfoPanel before running a prediction.
   *
   * @param {Object} geoJSON - GeoJSON geometry of the zone
   */
  getZoneStats: (geoJSON) =>
    apiJSON(`${BASE}/predict/zone/stats`, {
      method: 'POST',
      body:   JSON.stringify({ geometry: geoJSON }),
    }),

  /**
   * POST /predict/zone
   * Run the UHI prediction model over the selected zone.
   * Returns a base64-encoded PNG image + bounds + stats.
   *
   * @param {Object} body - { geometry, t_base, objects[] }
   */
  predictZone: (body) =>
    apiJSON(`${BASE}/predict/zone`, {
      method: 'POST',
      body:   JSON.stringify(body),
    }),

  /**
   * POST /predict/download
   * Download a layer as GeoTIFF, optionally cropped to a geometry.
   *
   * @param {string}      layerId  - Frontend layer ID
   * @param {Object|null} geometry - GeoJSON crop geometry, or null for full map
   * @returns {Promise<Blob>} Raw GeoTIFF blob
   */
  downloadLayer: (layerId, geometry) =>
    apiBlob(`${BASE}/predict/download`, {
      method: 'POST',
      body:   JSON.stringify({ layer: toBackendLayer(layerId), geometry }),
    }),
}
