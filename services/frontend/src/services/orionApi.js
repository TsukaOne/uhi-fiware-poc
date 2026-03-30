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

  /**
   * GET /ngsi-ld/v1/entities?type=TemperatureSensor&local=true
   * Fetch all temperature sensor entities directly from Orion-LD.
   *
   * Returns normalized sensor objects matching the shape expected by
   * useSensorMarkers: { station_id, station_name, temperature, latitude, longitude, ... }
   *
   * @returns {Promise<Array>} Array of normalized sensor objects
   */
  getTemperatureSensors: async () => {
    const entities = await apiJSON(
      `${BASE}/ngsi-ld/v1/entities?type=TemperatureSensor&limit=100&local=true`,
      { headers: { Accept: 'application/json' } }
    )
    return (entities || []).map(_ngsiToSensor)
  },
}


/**
 * Convert an NGSI-LD TemperatureSensor entity into a flat sensor object.
 */
function _ngsiToSensor(entity) {
  const coords = entity.location?.value?.coordinates || []
  return {
    station_id:     entity.stationId?.value     ?? entity.id,
    station_name:   entity.stationName?.value    ?? '',
    provider:       entity.provider?.value       ?? 'unknown',
    temperature:    entity.temperature?.value    ?? null,
    humidity:       entity.humidity?.value       ?? null,
    pressure:       entity.pressure?.value       ?? null,
    wind_speed:     entity.windSpeed?.value      ?? null,
    wind_direction: entity.windDirection?.value  ?? null,
    observed_at:    entity.temperature?.observedAt ?? '',
    latitude:       coords[1] ?? null,
    longitude:      coords[0] ?? null,
    status:         entity.status?.value         ?? 'Unknown',
    fallback:       entity.fallback?.value       ?? false,
  }
}
