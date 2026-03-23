/**
 * api.js — Base HTTP fetch wrapper.
 *
 * All API calls in this project go through this module so that:
 *  - Error handling is consistent across the entire codebase
 *  - The Content-Type default is set once
 *  - HTTP errors produce readable Error objects (not silent failures)
 *
 * Usage:
 *   import { apiJSON, apiBlob } from '../services/api.js'
 *   const data = await apiJSON('/prediction/vlinder/t_base')
 *   const blob = await apiBlob('/prediction/predict/download', { method: 'POST', body: ... })
 */

/**
 * Core fetch wrapper. Throws an Error on non-2xx responses.
 * On error, the response body text is included in the error message for easier debugging.
 *
 * @param {string} url
 * @param {RequestInit} [options]
 * @returns {Promise<Response>} The raw Response (body NOT yet consumed)
 */
export async function apiFetch(url, options = {}) {
  const resp = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })

  if (!resp.ok) {
    // Read the body once for the error message, then throw
    const errorBody = await resp.text().catch(() => '')
    throw new Error(`${resp.status}${errorBody ? ': ' + errorBody : ''}`)
  }

  return resp
}

/**
 * Fetch a JSON response.
 *
 * @param {string} url
 * @param {RequestInit} [options]
 * @returns {Promise<any>} Parsed JSON body
 */
export async function apiJSON(url, options = {}) {
  const resp = await apiFetch(url, options)
  return resp.json()
}

/**
 * Fetch a binary (Blob) response — used for file downloads.
 *
 * @param {string} url
 * @param {RequestInit} [options]
 * @returns {Promise<Blob>}
 */
export async function apiBlob(url, options = {}) {
  const resp = await apiFetch(url, options)
  return resp.blob()
}
