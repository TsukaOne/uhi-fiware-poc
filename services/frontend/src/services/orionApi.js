import { apiJSON } from './api.js'

const BASE = '/orion'

// NGSI-LD entity ID for the UHI prediction model metadata
const UHI_ENTITY_ID = 'urn:ngsi-ld:UHIHeatMap:XGBoost:brussels:2024'

/**
 * orionApi — Endpoints of the Orion NGSI-LD context broker.
 *
 * Base URL: /orion  (proxied by Vite/nginx to http://localhost:1026)
 *
 * Usage:
 *   import { orionApi } from '../services/orionApi.js'
 *   const entity = await orionApi.getUhiEntity()
 */
export const orionApi = {

  /**
   * GET /ngsi-ld/v1/entities/{id}?local=true
   * Fetch the UHI prediction model entity from Orion.
   * Used to retrieve the value range (min/max) for the UHI layer colour scale.
   *
   * @returns {Promise<Object>} Raw NGSI-LD entity
   */
  getUhiEntity: () =>
    apiJSON(
      `${BASE}/ngsi-ld/v1/entities/${UHI_ENTITY_ID}?local=true`,
      { headers: { Accept: 'application/json' } }
    ),
}
