"""
UHI Prediction Service

Generates a UHI heat map GeoTIFF from trained XGBoost model.
Input layer paths are resolved from Orion-LD at runtime.
Result is registered in Orion as a UHIHeatMap entity.

Routes:
  POST /predict/map         → launch prediction in background
  GET  /predict/map/status  → poll progress
"""

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
import joblib
import numpy as np
import rasterio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from rasterio.enums import Resampling
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import Window
from concurrent.futures import ThreadPoolExecutor, as_completed
from scipy.ndimage import distance_transform_edt

# ---------------------------------------------------------------------------
# These constants are already defined in main.py — import them from there
# when integrating. They are repeated here for standalone clarity.
# ---------------------------------------------------------------------------
import os

from algorithm.domain.layer_decoder import LayerDecoder

ORION_URL   = os.getenv("ORION_URL",   "http://orion:1026")
MODEL_PATH  = Path(os.getenv("MODEL_PATH",  "/data/models"))
OUTPUT_PATH = Path(os.getenv("DATA_PROCESSED_PATH", "/data/processed"))

NDVI_ENTITY_ID            = os.getenv("NDVI_ENTITY_ID",            "urn:ngsi-ld:GeoSpatialLayer:NDVI:brussels:2024")
NDWI_ENTITY_ID            = os.getenv("NDWI_ENTITY_ID",            "urn:ngsi-ld:GeoSpatialLayer:NDWI:brussels:2024")
NDBI_ENTITY_ID            = os.getenv("NDBI_ENTITY_ID",            "urn:ngsi-ld:GeoSpatialLayer:NDBI:brussels:2024")
DTM_ENTITY_ID             = os.getenv("DTM_ENTITY_ID",             "urn:ngsi-ld:GeoSpatialLayer:DTM:brussels:2024")
DSM_ENTITY_ID             = os.getenv("DSM_ENTITY_ID",             "urn:ngsi-ld:GeoSpatialLayer:DSM:brussels:2024")
BUILDING_HEIGHT_ENTITY_ID = os.getenv("BUILDING_HEIGHT_ENTITY_ID", "urn:ngsi-ld:GeoSpatialLayer:BuildingHeight:brussels:2024")
IMPERVIOUSNESS_ENTITY_ID  = os.getenv("IMPERVIOUSNESS_ENTITY_ID",  "urn:ngsi-ld:GeoSpatialLayer:Imperviousness:brussels:2024")
ALBEDO_ENTITY_ID          = os.getenv("ALBEDO_ENTITY_ID",          "urn:ngsi-ld:GeoSpatialLayer:Albedo:brussels:2024")
LST_ENTITY_ID             = os.getenv("LST_ENTITY_ID",             "urn:ngsi-ld:GeoSpatialLayer:LST:brussels:2024")

NGSI_LD_CONTEXT = "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"

# ---------------------------------------------------------------------------
# Processing constants
# ---------------------------------------------------------------------------
TILE_ROWS      = 4096
TILE_COLS      = 4096
TILE_WORKERS     = min(os.cpu_count() or 4, 8)
COG_BLOCKSIZE  = 512
OVERVIEW_FACTORS = [2, 4, 8, 16, 32]
NODATA_THRESHOLD = -1e10

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prediction state — thread-safe singleton
# ---------------------------------------------------------------------------
class _PredictionState:
    """Tracks a single running prediction job."""

    def __init__(self):
        self._lock        = threading.Lock()
        self._status      = "idle"      # idle | running | success | failed
        self._progress    = ""
        self._started_at: Optional[datetime] = None
        self._finished_at: Optional[datetime] = None
        self._result_path: Optional[str] = None
        self._entity_id:   Optional[str] = None
        self._error:       Optional[str] = None

    def start(self):
        with self._lock:
            self._status      = "running"
            self._progress    = "Starting…"
            self._started_at  = datetime.now(timezone.utc)
            self._finished_at = None
            self._result_path = None
            self._entity_id   = None
            self._error       = None

    def update(self, progress: str):
        with self._lock:
            self._progress = progress

    def succeed(self, result_path: str, entity_id: str):
        with self._lock:
            self._status      = "success"
            self._finished_at = datetime.now(timezone.utc)
            self._result_path = result_path
            self._entity_id   = entity_id
            self._progress    = "Done"

    def fail(self, error: str):
        with self._lock:
            self._status      = "failed"
            self._finished_at = datetime.now(timezone.utc)
            self._error       = error
            self._progress    = f"Error: {error}"

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "status":      self._status,
                "progress":    self._progress,
                "started_at":  self._started_at.isoformat()  if self._started_at  else None,
                "finished_at": self._finished_at.isoformat() if self._finished_at else None,
                "duration_seconds": (
                    (self._finished_at - self._started_at).total_seconds()
                    if self._started_at and self._finished_at else None
                ),
                "result_path": self._result_path,
                "entity_id":   self._entity_id,
                "error":       self._error,
            }

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._status == "running"


prediction_state = _PredictionState()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class MapResponse(BaseModel):
    status:  str
    message: str


class MapStatusResponse(BaseModel):
    status:           str
    progress:         str
    started_at:       Optional[str]
    finished_at:      Optional[str]
    duration_seconds: Optional[float]
    result_path:      Optional[str]
    entity_id:        Optional[str]
    error:            Optional[str]

# ---------------------------------------------------------------------------
# Orion helpers
# ---------------------------------------------------------------------------
async def _fetch_entity(entity_id: str) -> dict:
    url = f"{ORION_URL}/ngsi-ld/v1/entities/{entity_id}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, params={"local": "true"},
                             headers={"Accept": "application/json"})
    if r.status_code == 404:
        raise HTTPException(404, f"Entity {entity_id} not found in Orion. Has ingestion run?")
    if r.status_code != 200:
        raise HTTPException(502, f"Orion returned {r.status_code} for {entity_id}: {r.text}")
    return r.json()


def _extract_path(entity: dict) -> Path:
    value = entity.get("filePath", {}).get("value")
    if not value:
        raise HTTPException(502, f"Entity {entity.get('id')} has no filePath property")
    p = Path(value)
    if not p.exists():
        raise HTTPException(404, f"File {p} (entity {entity.get('id')}) not found on disk")
    return p


async def _resolve_all_layers() -> dict[str, Path]:
    """Fetch all nine input layer paths from Orion."""
    logger.info("Resolving input layers from Orion for prediction…")
    layer_map = {
        "ndvi":            NDVI_ENTITY_ID,
        "ndwi":            NDWI_ENTITY_ID,
        "ndbi":            NDBI_ENTITY_ID,
        "dtm":             DTM_ENTITY_ID,
        "dsm":             DSM_ENTITY_ID,
        "building_height": BUILDING_HEIGHT_ENTITY_ID,
        "imperviousness":  IMPERVIOUSNESS_ENTITY_ID,
        "albedo":          ALBEDO_ENTITY_ID,
        "lst":             LST_ENTITY_ID,
    }
    paths: dict[str, Path] = {}
    for name, eid in layer_map.items():
        entity     = await _fetch_entity(eid)
        paths[name] = _extract_path(entity)
        logger.info(f"  {name:20s} → {paths[name]}")
    return paths


async def _register_heatmap_entity(prediction_path: Path, input_entity_ids: list[str],uhi_min: float,uhi_max: float,) -> str:
    """Create or update the UHIHeatMap entity in Orion."""
    entity_id = "urn:ngsi-ld:UHIHeatMap:XGBoost:brussels:2024"

    # Bounding box in WGS-84
    bbox = None
    try:
        with rasterio.open(prediction_path) as src:
            l, b, r, t = transform_bounds(src.crs, "EPSG:4326",
                                          *src.bounds)
            bbox = {
                "type": "Polygon",
                "coordinates": [[[l, b], [r, b], [r, t], [l, t], [l, b]]],
            }
    except Exception as exc:
        logger.warning(f"Could not extract bbox: {exc}")

    entity: dict = {
        "@context": NGSI_LD_CONTEXT,
        "id":   entity_id,
        "type": "UHIHeatMap",
        "name":          {"type": "Property", "value": "UHI XGBoost Heat Map Brussels 2024"},
        "modelType":     {"type": "Property", "value": "XGBoost"},
        "modelVersion":  {"type": "Property", "value": "xgb_uhi_latest"},
        "dateGenerated": {"type": "Property", "value": datetime.now(timezone.utc).isoformat()},
        "inputLayers":   {"type": "Property", "value": input_entity_ids},
        "filePath":      {"type": "Property", "value": str(prediction_path)},
        "geoserverLayer":    {"type": "Property", "value": "uhi:uhi_xgb_heatmap"},
        "publishToGeoserver":{"type": "Property", "value": True},
        "valueRange": {
            "type":  "Property",
            "value": {
                "min":         round(uhi_min, 3),
                "max":         round(uhi_max, 3),
                "unit":        "°C",
                "description": (
                    "UHI intensity — land surface temperature delta "
                    "between pixel and rural reference (LST_pixel - LST_rural). "
                    "Positive values indicate urban heat excess."
                ),
                "encoding": (
                    f"uint8 [0–254] → [{round(uhi_min,3)}–{round(uhi_max,3)}] °C, "
                    "255 = nodata"
                ),
            },
        },

    }
    if bbox:
        entity["boundingBox"] = {"type": "GeoProperty", "value": bbox}

    headers = {"Content-Type": "application/ld+json", "Accept": "application/ld+json"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(f"{ORION_URL}/ngsi-ld/v1/entities",
                              json=entity, headers=headers)
        if r.status_code == 201:
            logger.info(f"Created UHIHeatMap entity: {entity_id}")
        elif r.status_code == 409:
            patch = {k: v for k, v in entity.items()
                     if k not in ("@context", "id", "type")}
            patch["@context"] = NGSI_LD_CONTEXT
            r = await client.patch(
                f"{ORION_URL}/ngsi-ld/v1/entities/{entity_id}/attrs",
                json=patch, headers=headers)
            if r.status_code in (200, 204):
                logger.info(f"Updated UHIHeatMap entity: {entity_id}")
            else:
                logger.error(f"Failed to patch entity: {r.status_code} {r.text}")
        else:
            logger.error(f"Failed to create entity: {r.status_code} {r.text}")

    return entity_id

def _sample_distance(
    dist_raster: np.ndarray,
    rows: np.ndarray,
    cols: np.ndarray,
    downsample: int = 4,
) -> np.ndarray:
    """Look up distance values for full-resolution pixel coordinates."""
    ds_rows = np.clip(rows // downsample, 0, dist_raster.shape[0] - 1)
    ds_cols = np.clip(cols // downsample, 0, dist_raster.shape[1] - 1)
    return dist_raster[ds_rows, ds_cols]


def _process_tile(
    row_off: int,
    col_off: int,
    total_height: int,
    total_width: int,
    paths: dict[str, Path],
    ref_transform,
    ref_crs,
    artifact: dict,
    xgb_model,
    uhi_min: float,
    uhi_max: float,
    dist_water: np.ndarray,
    dist_park: np.ndarray,
) -> tuple[Window, np.ndarray]:
    """
    Read, decode, predict and encode one tile.
    Returns (window, uint8_array) so the writer thread can flush it.
    """
    tile_h = min(TILE_ROWS, total_height - row_off)
    tile_w = min(TILE_COLS, total_width  - col_off)
    window = Window(col_off, row_off, tile_w, tile_h)

    # ── Read all layers in parallel (I/O-bound) ──────────────────────
    decoded_layers = _read_tile_parallel(
        paths         = paths,
        window        = window,
        ref_transform = ref_transform,
        ref_crs       = ref_crs,
    )

    # ── Validity mask: all layers must have data ─────────────────────
    first_array = next(iter(decoded_layers.values()))[0]
    valid = np.ones(first_array.shape, dtype=bool)
    for layer_name, (decoded, nodata_mask) in decoded_layers.items():
        valid &= ~nodata_mask

    lst_f, _ = decoded_layers["lst"]
    valid &= np.isfinite(lst_f) & (lst_f > 0)

    out = np.full((tile_h, tile_w), 255, dtype=np.uint8)

    n_valid = int(valid.sum())
    if n_valid > 0:
        idx = np.flatnonzero(valid)

        # Global pixel coordinates for distance lookup
        rr_tile, cc_tile = np.unravel_index(idx, (tile_h, tile_w))
        rr_g = rr_tile + row_off
        cc_g = cc_tile + col_off

        dw = _sample_distance(dist_water, rr_g, cc_g)
        dp = _sample_distance(dist_park,  rr_g, cc_g)

        X = np.column_stack([
            decoded_layers["ndvi"][0].ravel()[idx],
            decoded_layers["ndwi"][0].ravel()[idx],
            decoded_layers["ndbi"][0].ravel()[idx],
            decoded_layers["dtm"][0].ravel()[idx],
            decoded_layers["dsm"][0].ravel()[idx],
            decoded_layers["building_height"][0].ravel()[idx],
            decoded_layers["imperviousness"][0].ravel()[idx],
            decoded_layers["albedo"][0].ravel()[idx],
            dw,
            dp,
        ]).astype(np.float32)

        y_pred = xgb_model.predict(X).astype(np.float32)

        if uhi_max > uhi_min:
            heat_risk = (y_pred - uhi_min) / (uhi_max - uhi_min)
        else:
            heat_risk = np.zeros_like(y_pred)
        heat_risk = np.clip(heat_risk, 0.0, 1.0)

        encoded = (heat_risk * 254).astype(np.uint8)
        out[rr_tile, cc_tile] = encoded

    return window, out
# ---------------------------------------------------------------------------
# Background thread — real XGBoost tiled inference
# ---------------------------------------------------------------------------
def _prediction_job(paths: dict[str, Path], loop: asyncio.AbstractEventLoop) -> None:
    """
    Runs in a daemon thread. Steps:
      1. Load model from disk
      2. Open reference grid (NDVI), pre-compute distance rasters
      3. For each tile: read all 9 layers → build 10-feature matrix → predict → encode uint8
      4. Write COG GeoTIFF
      5. Build overviews
      6. Register entity in Orion
    """
    try:
        logger.info("=== Prediction job started ===")

        # ── 1. Load model ────────────────────────────────────────────
        prediction_state.update("Loading XGBoost model…")
        model_file = MODEL_PATH / "xgb_uhi_latest.joblib"
        if not model_file.exists():
            raise FileNotFoundError(
                f"No trained model found at {model_file}. "
                "Run POST /training/start first."
            )
        artifact       = joblib.load(model_file)
        xgb_model      = artifact["model"]
        feature_names  = artifact["feature_names"]
        xgb_model.set_params(nthread=os.cpu_count())
        logger.info(f"Model loaded — features: {feature_names}")

        uhi_min = float(artifact.get("uhi_min",  0.0))
        uhi_max = float(artifact.get("uhi_max", 1.0))

        # ── Log training metrics & feature importance ────────────────
        importances = xgb_model.feature_importances_
        logger.info("── Model metrics ──────────────────────────────────")
        logger.info(f"  UHI range     : [{uhi_min:.3f}, {uhi_max:.3f}] °C")
        logger.info(f"  Avg UHI       : {artifact.get('avg_uhi', 'N/A')}")
        logger.info(f"  Created at    : {artifact.get('created_at', 'N/A')}")
        logger.info("── Feature importance ─────────────────────────────")
        sorted_idx = np.argsort(importances)[::-1]
        for i in sorted_idx:
            logger.info(f"  {feature_names[i]:22s}  {importances[i]:.4f}")

        # ── 2. Reference grid from NDVI ──────────────────────────────
        ndvi_path = paths["ndvi"]
        with rasterio.open(ndvi_path) as ref:
            ref_crs = ref.crs
            ref_transform = ref.transform
            total_height = ref.height
            total_width = ref.width

        logger.info(
            f"Reference grid: {total_width}×{total_height} px, "
        )

        # ── 2b. Pre-compute distance rasters ────────────────────────
        prediction_state.update("Pre-computing distance rasters…")
        DOWNSAMPLE = 4
        ds_h = total_height // DOWNSAMPLE
        ds_w = total_width // DOWNSAMPLE
        pixel_size = abs(ref_transform.a)

        logger.info(f"Pre-computing distance_to_water ({ds_h}×{ds_w} downsampled)…")
        with rasterio.open(paths["ndwi"]) as src:
            ndwi_ds = src.read(
                1, out_shape=(ds_h, ds_w),
                resampling=Resampling.bilinear,
            ).astype(np.float32)
        ndwi_decoded = (ndwi_ds / 254.0) * 2.0 - 1.0
        water_mask = ndwi_decoded > 0.0
        dist_water = distance_transform_edt(~water_mask).astype(np.float32)
        dist_water *= (pixel_size * DOWNSAMPLE)
        del ndwi_ds, ndwi_decoded, water_mask
        logger.info(f"  distance_to_water range: [{dist_water.min():.0f}, {dist_water.max():.0f}] m")

        logger.info(f"Pre-computing distance_to_park ({ds_h}×{ds_w} downsampled)…")
        with rasterio.open(paths["ndvi"]) as src:
            ndvi_ds = src.read(
                1, out_shape=(ds_h, ds_w),
                resampling=Resampling.bilinear,
            ).astype(np.float32)
        ndvi_decoded = (ndvi_ds / 254.0) * 2.0 - 1.0
        park_mask = ndvi_decoded > 0.4
        dist_park = distance_transform_edt(~park_mask).astype(np.float32)
        dist_park *= (pixel_size * DOWNSAMPLE)
        del ndvi_ds, ndvi_decoded, park_mask
        logger.info(f"  distance_to_park range: [{dist_park.min():.0f}, {dist_park.max():.0f}] m")

        OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
        prediction_path = OUTPUT_PATH / "uhi_xgb_heatmap_brussels_2024.tif"

        profile = {
            "driver":    "GTiff",
            "dtype":     "uint8",
            "count":     1,
            "nodata":    255,
            "crs":       ref_crs,
            "transform": ref_transform,
            "height":    total_height,
            "width":     total_width,
            "compress":  "deflate",
            "predictor": 2,
            "tiled":     True,
            "blockxsize": COG_BLOCKSIZE,
            "blockysize": COG_BLOCKSIZE,
        }

         # ── 3. Tiled inference (parallel) ────────────────────────────
        tile_offsets = [
            (r, c)
            for r in range(0, total_height, TILE_ROWS)
            for c in range(0, total_width,  TILE_COLS)
        ]
        total_tiles = len(tile_offsets)
        logger.info(f"Total tiles: {total_tiles}  (workers: {TILE_WORKERS})")

        write_lock = threading.Lock()
        tile_count = 0

        with rasterio.open(prediction_path, "w", **profile) as dst:
            with ThreadPoolExecutor(max_workers=TILE_WORKERS) as pool:
                futures = {
                    pool.submit(
                        _process_tile,
                        row_off, col_off,
                        total_height, total_width,
                        paths,
                        ref_transform, ref_crs,
                        artifact, xgb_model,
                        uhi_min, uhi_max,
                        dist_water, dist_park,
                    ): (row_off, col_off)
                    for row_off, col_off in tile_offsets
                }

                for future in as_completed(futures):
                    window, out = future.result()   # raises on worker error
                    with write_lock:
                        dst.write(out, 1, window=window)

                    tile_count += 1
                    if tile_count % 50 == 0 or tile_count == total_tiles:
                        pct = tile_count / total_tiles * 100
                        msg = f"Inference {tile_count}/{total_tiles} tiles ({pct:.0f}%)"
                        prediction_state.update(msg)
                        logger.info(msg)
            dst.update_tags(
                LAYER_TYPE  = "UHI_HEATMAP",
                MODEL_TYPE  = "XGBoost",
                MODEL_FILE  = str(model_file),
                FEATURES    = ",".join(feature_names),
                VALUE_RANGE = f"{round(uhi_min,3)} to {round(uhi_max,3)} °C (LST_pixel - LST_rural)",
                ENCODING    = f"uint8 [0–254] → [{round(uhi_min,3)}–{round(uhi_max,3)}] °C, 255=nodata",
                GENERATED_AT= datetime.now(timezone.utc).isoformat(),
            )

        # ── 4. Overviews ─────────────────────────────────────────────
        prediction_state.update("Building overviews…")
        with rasterio.open(prediction_path, "r+") as ds:
            ds.build_overviews(OVERVIEW_FACTORS, Resampling.average)
            ds.update_tags(ns="rio_overview", resampling="average")
        logger.info(f"GeoTIFF saved: {prediction_path}")

        # ── 5. Register in Orion (async from sync thread) ────────────
        prediction_state.update("Registering UHIHeatMap entity in Orion…")
        input_ids = [
            NDVI_ENTITY_ID, NDWI_ENTITY_ID, NDBI_ENTITY_ID,
            DTM_ENTITY_ID, DSM_ENTITY_ID, BUILDING_HEIGHT_ENTITY_ID,
            IMPERVIOUSNESS_ENTITY_ID, ALBEDO_ENTITY_ID, LST_ENTITY_ID,
        ]
        future = asyncio.run_coroutine_threadsafe(
            _register_heatmap_entity(prediction_path, input_ids,uhi_min, uhi_max),
            loop,
        )
        entity_id = future.result(timeout=30)
        logger.info(f"Registered: {entity_id}")

        prediction_state.succeed(str(prediction_path), entity_id)
        logger.info("=== Prediction job completed ===")

    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}"
        logger.exception("Prediction job failed")
        prediction_state.fail(msg)


# ---------------------------------------------------------------------------
# Tiled parallel reader (one thread per layer, I/O-bound)
# ---------------------------------------------------------------------------
def _read_tile_parallel(
    paths: dict[str, Path],
    window: Window,
    ref_transform,
    ref_crs,
) -> dict[str, np.ndarray]:
    """
    Read all layers for one tile in parallel.
    Layers already on the NDVI reference grid are read natively;
    others (dtm, building_height, lst) are reprojected on the fly.
    """
    native = {"ndvi", "ndwi", "ndbi"}   # same CRS/resolution as reference

    def _load(name: str, path: Path) -> tuple[str, tuple[np.ndarray, np.ndarray]]:
        decoder = LayerDecoder()
        if name in native:
            with rasterio.open(path) as src:
                raw = src.read(
                    1, window=window, boundless=True,
                    fill_value=src.nodata if src.nodata is not None else 0,
                    out_dtype=np.float32,
                )
            decoded, nodata_mask = decoder.decode(
                raw=raw,
                layer_name=name,
                raster_path=str(path),
            )
            return name, (decoded, nodata_mask)
        # Reproject to reference tile extent
        h, w   = window.height, window.width
        raw    = np.full((h, w), np.nan, dtype=np.float32)
        bounds = rasterio.windows.bounds(window, ref_transform)
        dst_tf = rasterio.transform.from_bounds(*bounds, width=w, height=h)
        with rasterio.open(path) as src:
            reproject(
                source        = rasterio.band(src, 1),
                destination   = raw,
                src_transform = src.transform,
                src_crs       = src.crs,
                src_nodata    = src.nodata,
                dst_transform = dst_tf,
                dst_crs       = ref_crs,
                dst_nodata    = np.nan,
                resampling    = Resampling.bilinear,
            )
        decoded, nodata_mask = decoder.decode(
            raw=raw,
            layer_name=name,
            raster_path=str(path),
        )
        return name, (decoded, nodata_mask)

    results: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    with ThreadPoolExecutor(max_workers=min(len(paths), 6)) as pool:
        for name, result in pool.map(lambda kv: _load(*kv), paths.items()):
            results[name] = result
    return results