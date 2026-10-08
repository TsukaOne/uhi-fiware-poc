import * as Cesium from 'cesium'

const TYPE_PROPERTY = 'TYPE'
const ROOF_TYPE = 'ROOFSURFACE'

const BUILDING_ID_PROPERTY = 'BUSOLID_ID'

const SURFACE_ID_PROPERTY = 'INSPIRE_ID'

/** Per-surface centroid, used to make the assignment spatially coherent */
const LAT_PROPERTY = 'Latitude'
const LON_PROPERTY = 'Longitude'


/**
 * Share of roofs left untinted. High on purpose: the colour code is meant to
 * point at a handful of rooftops per block, not to repaint the city.
 */
const UNASSIGNED_PERCENT = 72

/**
 * Rough diameter, in metres, of a patch sharing one rooftop function.
 *
 * Functions are drawn from a Worley (cellular) noise field over the building
 * centroids rather than from the building id, so neighbouring roofs mostly
 * agree and the map reads as zones instead of confetti. Raise this for broader
 * districts, lower it for a finer mosaic.
 */
const CLUSTER_SIZE_M = 400

// Metres per degree around Brussels. A constant is plenty: over a 20 km city
// the latitude-dependent error is far below one cell.
const M_PER_DEG_LAT = 111_320
const M_PER_DEG_LON = M_PER_DEG_LAT * Math.cos(50.85 * Math.PI / 180)

export const ROOF_FUNCTIONS = [
  {
    id: 'green',
    label: 'Nature and biodiversity',
    description: 'Vegetation, habitat, ecological connections, shade and cleaner air.',
    color: '#2E9E4F',
  },
  {
    id: 'blue',
    label: 'Water management',
    description: 'Rainwater storage, buffering, reuse and reduced pressure on drainage systems.',
    color: '#2F80D6',
  },
  {
    id: 'yellow',
    label: 'Energy transition',
    description: 'Solar or heat generation, storage, insulation and thermal comfort.',
    color: '#F2C230',
  },
  {
    id: 'red',
    label: 'Social and community',
    description: 'Places for meeting, culture, learning, recreation, food growing or play.',
    color: '#D64545',
  },
  {
    id: 'orange',
    label: 'Mobility',
    description: 'Active-travel links, logistics, safety routes or other locally suitable mobility uses.',
    color: '#E8802B',
  },
  {
    id: 'purple',
    label: 'Densification',
    description: 'New housing, workspaces, facilities or other usable floor area where feasible.',
    color: '#8B5CF6',
  },
  {
    id: 'grey',
    label: 'Utilities and infrastructure',
    description: 'Technical equipment and services such as HVAC, telecoms or safety installations.',
    // Dark slate on purpose: a mid grey, once brightened, lands on the
    // tileset's own colour and an assigned roof would read as an untinted one.
    color: '#3D4552',
  },
]

// Tints are brighter than the legend swatches: Cesium multiplies them with the
// tileset's own light grey, which would otherwise mute every colour.
const TINTS = ROOF_FUNCTIONS.map(f =>
  Cesium.Color.fromCssColorString(f.color).brighten(0.5, new Cesium.Color())
)

// The legend shows the tint that actually lands on the roofs, not the authored
// base colour — otherwise the dark slate of "utilities" would vanish against
// the panel while being perfectly visible on the map.
ROOF_FUNCTIONS.forEach((fn, i) => { fn.swatch = TINTS[i].toCssHexString() })

/** Restores a feature to the tileset's own appearance */
const NO_TINT = Cesium.Color.WHITE

/**
 * @param {Object} options
 * @param {() => Cesium.Cesium3DTileset} options.getBuildingTileset - Returns the building tileset (may be null)
 * @param {() => Cesium.Viewer}          options.getViewer          - Returns the Cesium viewer
 */
export function useRoofFunctions({ getBuildingTileset, getViewer }) {

  let active = false
  let removeTileVisible = null

  /**
   * Tile contents already processed for the current session. Keyed by the
   * content object, which Cesium replaces on unload/reload, so an evicted tile
   * is naturally re-tinted when it comes back.
   */
  let paintedContents = new WeakSet()


  // ── Public API ──────────────────────────────────────────────────────────────

  function enable() {
    const tileset = getBuildingTileset()
    if (active || !tileset) return

    active = true
    paintedContents = new WeakSet()

    // tileVisible fires every frame for every visible tile; the WeakSet keeps
    // the actual work to once per loaded content.
    removeTileVisible = tileset.tileVisible.addEventListener(_paintTile)

    // Tiles already resident were loaded before the listener existed
    _repaintLoadedTiles(tileset, _paintContent)
  }

  function disable() {
    if (!active) return
    active = false

    if (removeTileVisible) {
      removeTileVisible()
      removeTileVisible = null
    }

    const tileset = getBuildingTileset()
    if (tileset) _repaintLoadedTiles(tileset, _clearContent)

    paintedContents = new WeakSet()
    getViewer()?.scene.requestRender()
  }

  function isActive() {
    return active
  }

  /**
   * The Multiroof function of one picked feature, or null when the feature is
   * not a roof or was left unassigned. Lets the UI explain a clicked roof.
   *
   * @param {Cesium.Cesium3DTileFeature} feature
   */
  function getFeatureFunction(feature) {
    if (!feature || typeof feature.getProperty !== 'function') return null
    if (feature.getProperty(TYPE_PROPERTY) !== ROOF_TYPE) return null
    return _functionFor(feature)
  }


  // ── Painting ────────────────────────────────────────────────────────────────

  function _paintTile(tile) {
    if (!active) return
    _forEachContent(tile, _paintContent)
  }

  function _paintContent(content) {
    if (paintedContents.has(content)) return
    paintedContents.add(content)

    const count = content.featuresLength
    for (let i = 0; i < count; i++) {
      const feature = content.getFeature(i)
      if (!feature || feature.getProperty(TYPE_PROPERTY) !== ROOF_TYPE) continue

      const fn = _functionFor(feature)
      if (fn) feature.color = TINTS[fn.index]
    }
  }

  function _clearContent(content) {
    const count = content.featuresLength
    for (let i = 0; i < count; i++) {
      const feature = content.getFeature(i)
      if (feature) feature.color = NO_TINT
    }
  }

  /**
   * Walk every loaded tile of the tileset and hand its content to `visit`.
   * Used on enable (tiles loaded before the listener) and on disable (tiles
   * that must be reset).
   */
  function _repaintLoadedTiles(tileset, visit) {
    // `_selectedTiles` is not public API, so drive it from the root instead.
    const stack = [tileset.root]
    while (stack.length) {
      const tile = stack.pop()
      if (!tile) continue
      if (tile.contentReady) _forEachContent(tile, visit)
      if (tile.children) stack.push(...tile.children)
    }
    getViewer()?.scene.requestRender()
  }

  function _forEachContent(tile, visit) {
    const content = tile.content
    if (!content) return

    // A tile may hold several inner contents; b3dm tiles hold exactly one
    if (content.innerContents) {
      content.innerContents.forEach(inner => {
        if (inner?.featuresLength) visit(inner)
      })
    } else if (content.featuresLength) {
      visit(content)
    }
  }


  // ── Assignment ──────────────────────────────────────────────────────────────

  /**
   * Deterministically map a roof feature onto a Multiroof function, or null
   * when it is one of the deliberately unassigned roofs.
   *
   * Keyed on the building solid so every roof pan of a building agrees, and
   * stable across reloads because it is a pure hash — no randomness.
   */
  function _functionFor(feature) {
    const key =
      feature.getProperty(BUILDING_ID_PROPERTY) ||
      feature.getProperty(SURFACE_ID_PROPERTY)

    if (!key) return null

    // Whether a roof carries a function at all stays a per-building decision,
    // so a zone keeps some bare roofs instead of being uniformly painted.
    if (_fnv1a(String(key)) % 100 < UNASSIGNED_PERCENT) return null

    // Which function it carries comes from where it stands, so neighbours agree.
    const lon = feature.getProperty(LON_PROPERTY)
    const lat = feature.getProperty(LAT_PROPERTY)

    const index = Number.isFinite(lon) && Number.isFinite(lat)
      ? _clusterIndex(lon, lat)
      // No centroid on this feature: fall back to the building id, which at
      // least keeps every pan of that roof consistent.
      : (_fnv1a(String(key)) >>> 8) % ROOF_FUNCTIONS.length

    return { ...ROOF_FUNCTIONS[index], index }
  }

  /**
   * Worley / cellular noise: each grid cell holds one jittered seed, and a
   * point takes the function of its nearest seed. The jitter is what keeps the
   * patches organic — a plain grid lookup would draw visible square blocks.
   *
   * @param {number} lon - Degrees east
   * @param {number} lat - Degrees north
   * @returns {number} Index into ROOF_FUNCTIONS
   */
  function _clusterIndex(lon, lat) {
    // Position in cell units, so distances are isotropic despite lon/lat scaling
    const x = (lon * M_PER_DEG_LON) / CLUSTER_SIZE_M
    const y = (lat * M_PER_DEG_LAT) / CLUSTER_SIZE_M

    const cellX = Math.floor(x)
    const cellY = Math.floor(y)

    let nearestDistance = Infinity
    let nearestHash = 0

    // The nearest seed is always in the 3x3 block around the point's own cell
    for (let dy = -1; dy <= 1; dy++) {
      for (let dx = -1; dx <= 1; dx++) {
        const gx = cellX + dx
        const gy = cellY + dy
        const hash = _hashCell(gx, gy)

        // Low 16 bits place the seed somewhere inside its cell
        const seedX = gx + (hash & 0xff) / 255
        const seedY = gy + ((hash >>> 8) & 0xff) / 255

        const distance = (seedX - x) ** 2 + (seedY - y) ** 2
        if (distance < nearestDistance) {
          nearestDistance = distance
          nearestHash = hash
        }
      }
    }

    // High bits pick the function, so seed placement and colour stay independent
    return (nearestHash >>> 16) % ROOF_FUNCTIONS.length
  }

  /** Hash a pair of signed cell coordinates into a well-mixed 32-bit value. */
  function _hashCell(x, y) {
    let hash = 0x811c9dc5
    hash = Math.imul(hash ^ (x & 0xffff), 0x01000193)
    hash = Math.imul(hash ^ ((x >> 16) & 0xffff), 0x01000193)
    hash = Math.imul(hash ^ (y & 0xffff), 0x01000193)
    hash = Math.imul(hash ^ ((y >> 16) & 0xffff), 0x01000193)

    // Avalanche, so neighbouring cells do not land on neighbouring functions
    hash ^= hash >>> 15
    hash = Math.imul(hash, 0x2545f491)
    hash ^= hash >>> 13
    return hash >>> 0
  }

  /** FNV-1a, 32-bit. Cheap, well spread, and identical on every run. */
  function _fnv1a(str) {
    let hash = 0x811c9dc5
    for (let i = 0; i < str.length; i++) {
      hash ^= str.charCodeAt(i)
      hash = Math.imul(hash, 0x01000193)
    }
    return hash >>> 0
  }


  return { enable, disable, isActive, getFeatureFunction }
}
