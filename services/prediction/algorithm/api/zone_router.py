"""
Zone Prediction Router — zone prediction, stats, pixel query, and download endpoints.
"""
from __future__ import annotations

import base64
import io
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import rasterio
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

from algorithm.application.zone_predictor import ZonePredictor

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request / Response schemas ────────────────────────────────────────────────

# Class for placing objects in the zone
class PlacedObject(BaseModel):
    type: str = Field(..., description="Object type key (e.g. 'tree_deciduous', 'building_residential')")
    lon: float = Field(..., description="Longitude (WGS84)")
    lat: float = Field(..., description="Latitude (WGS84)")

# Request for zone prediction, including geometry and placed objects
class ZonePredictionRequest(BaseModel):
    geometry: dict = Field(
        ...,
        description="GeoJSON geometry (Polygon) in WGS84. Must have 'type' and 'coordinates'.",
        examples=[{
            "type": "Polygon",
            "coordinates": [[[4.35, 50.84], [4.36, 50.84], [4.36, 50.85], [4.35, 50.85], [4.35, 50.84]]]
        }],
    )
    objects: list[PlacedObject] = Field(
        default_factory=list,
        description="List of 3D objects placed by the user in the zone",
    )

# Response schemas for prediction output and stats
class ZoneBounds(BaseModel):
    west: float
    south: float
    east: float
    north: float

# Response schemas for prediction output and stats
class ZonePredictionStats(BaseModel):
    mean_uhi: float
    min_uhi: float
    max_uhi: float
    pixel_count: int
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    duration_ms: Optional[float] = None
    uhi_range: Optional[dict] = None

# Response for zone prediction
class ZonePredictionResponse(BaseModel):
    status: str
    image_base64: str = Field(..., description="RGBA PNG image encoded as base64")
    bounds: ZoneBounds
    stats: ZonePredictionStats

# Request for zone stats
class ZoneStatsRequest(BaseModel):
    geometry: dict = Field(
        ...,
        description="GeoJSON geometry (Polygon) in WGS84.",
    )

# Response for zone stats
class LayerStat(BaseModel):
    mean: float
    min: float
    max: float
    std: float

# Response for zone stats
class ZoneStatsResponse(BaseModel):
    status: str
    layer_stats: dict[str, LayerStat]
    pixel_count: int
    bounds: ZoneBounds


# ── Dependency ────────────────────────────────────────────────────────────────

# Get the zone predictor singleton
def _get_zone_predictor() -> ZonePredictor:
    from main import zone_predictor
    return zone_predictor


# ── Endpoint ──────────────────────────────────────────────────────────────────
# POST /predict/zone - run prediction on a drawn zone with optional placed objects
@router.post("/predict/zone", response_model=ZonePredictionResponse)
async def predict_zone(
    request: ZonePredictionRequest,
    predictor: ZonePredictor = Depends(_get_zone_predictor),
):
    """
    Run UHI prediction on a user-drawn zone.

    Returns a colormapped RGBA PNG (base64) with geographic bounds,
    ready for overlay in Cesium as a SingleTileImageryProvider.
    """
    # Validate geometry
    geom = request.geometry
    if geom.get("type") != "Polygon" or not geom.get("coordinates"):
        raise HTTPException(
            422, "geometry must be a GeoJSON Polygon with 'type' and 'coordinates'"
        )

    try:
        result = await predictor.predict(
            geometry=geom,
            objects=[obj.model_dump() for obj in request.objects],
        )
    except FileNotFoundError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        logger.exception("Zone prediction failed")
        raise HTTPException(500, f"Prediction failed: {e}")

    image_b64 = base64.b64encode(result.png_bytes).decode("ascii")

    return ZonePredictionResponse(
        status="success",
        image_base64=image_b64,
        bounds=ZoneBounds(**result.bounds),
        stats=ZonePredictionStats(**result.stats),
    )


@router.post("/predict/zone/stats", response_model=ZoneStatsResponse)
async def zone_stats(
    request: ZoneStatsRequest,
    predictor: ZonePredictor = Depends(_get_zone_predictor),
):
    """
    Return decoded layer statistics (mean/min/max/std) for a drawn zone.
    No prediction — just reads and decodes the input rasters.
    """
    geom = request.geometry
    if geom.get("type") != "Polygon" or not geom.get("coordinates"):
        raise HTTPException(
            422, "geometry must be a GeoJSON Polygon with 'type' and 'coordinates'"
        )

    try:
        result = await predictor.compute_zone_stats(geometry=geom)
    except Exception as e:
        logger.exception("Zone stats computation failed")
        raise HTTPException(500, f"Zone stats failed: {e}")

    return ZoneStatsResponse(
        status="success",
        layer_stats={k: LayerStat(**v) for k, v in result.layer_stats.items()},
        pixel_count=result.pixel_count,
        bounds=ZoneBounds(**result.bounds),
    )


# ── Pixel value query ────────────────────────────────────────────────────────


class PixelValueRequest(BaseModel):
    lon: float = Field(..., description="Longitude (WGS84)")
    lat: float = Field(..., description="Latitude (WGS84)")


class PixelValueResponse(BaseModel):
    status: str
    lon: float
    lat: float
    values: dict[str, Optional[float]]


@router.post("/predict/pixel/value", response_model=PixelValueResponse)
async def pixel_value(
    request: PixelValueRequest,
    predictor: ZonePredictor = Depends(_get_zone_predictor),
):
    """Return decoded physical values for all layers at a single lon/lat."""
    try:
        result = await predictor.get_pixel_values(lon=request.lon, lat=request.lat)
    except Exception as e:
        logger.exception("Pixel value lookup failed")
        raise HTTPException(500, f"Pixel value lookup failed: {e}")

    return PixelValueResponse(
        status="success",
        lon=result.lon,
        lat=result.lat,
        values=result.values,
    )


# ── Single-layer global stats ────────────────────────────────────────────────


class SingleLayerStatsRequest(BaseModel):
    layer: str = Field(..., description="Layer name (e.g. 'ndvi', 'lst', 'uhi')")
    geometry: Optional[dict] = Field(
        None,
        description="Optional GeoJSON Polygon to clip. If null, computes over full raster.",
    )


class SingleLayerStatsResponse(BaseModel):
    status: str
    layer: str
    mean: float
    min: float
    max: float
    std: float
    pixel_count: int


@router.post("/predict/layer/stats", response_model=SingleLayerStatsResponse)
async def layer_stats(request: SingleLayerStatsRequest):
    """
    Return decoded statistics (mean/min/max/std) for a single layer.
    Decodes uint8 COG encoding to real physical float32 values using LayerDecoder.
    Optionally clips to a GeoJSON geometry (Polygon).
    """
    from algorithm.infrastructure.layer_resolver import LayerResolver
    from algorithm.config import Settings
    from algorithm.domain.layer_decoder import LayerDecoder, LAYER_SPECS

    layer = request.layer
    resolver: LayerResolver = _get_layer_resolver()
    settings: Settings = _get_settings()

    # Resolve file path
    if layer == "uhi":
        file_path = Path(settings.output_path) / "uhi_xgb_heatmap_brussels_2024.tif"
        if not file_path.exists():
            raise HTTPException(404, "UHI prediction output not found.")
    else:
        entity_ids = settings.all_layer_entity_ids
        if layer not in entity_ids:
            raise HTTPException(
                422,
                f"Unknown layer '{layer}'. Available: {list(entity_ids.keys()) + ['uhi']}",
            )
        try:
            paths = await resolver.resolve_required({layer: entity_ids[layer]})
            file_path = paths[layer]
        except Exception as e:
            raise HTTPException(503, f"Cannot resolve layer: {e}")

    # Read raster (optionally clipped) and decode to physical values
    try:
        with rasterio.open(file_path) as ds:
            # If geometry provided, clip to bounding box window
            if request.geometry is not None:
                geom = request.geometry
                if geom.get("type") != "Polygon" or not geom.get("coordinates"):
                    raise HTTPException(422, "geometry must be a GeoJSON Polygon")
                coords = geom["coordinates"][0]
                lons = [c[0] for c in coords]
                lats = [c[1] for c in coords]
                # Transform WGS84 bounds to raster CRS
                raster_bounds = transform_bounds("EPSG:4326", ds.crs, min(lons), min(lats), max(lons), max(lats))
                window = from_bounds(*raster_bounds, transform=ds.transform)
                raw = ds.read(1, window=window)
            else:
                raw = ds.read(1)

            # Decode uint8 → float32 using LayerDecoder
            decoder = LayerDecoder()
            if layer in LAYER_SPECS:
                decoded, nodata_mask = decoder.decode(raw, layer, raster_path=str(file_path))
                valid = decoded[~nodata_mask & np.isfinite(decoded)]
            else:
                # UHI or unknown: already float-like, apply standard nodata filtering
                data = raw.astype(np.float64)
                nodata = ds.nodata
                if nodata is not None:
                    valid = data[data != nodata]
                else:
                    valid = data[np.isfinite(data)]
                valid = valid[np.isfinite(valid)]

            if len(valid) == 0:
                raise HTTPException(404, f"Layer '{layer}' has no valid pixels in the selected area.")

            return SingleLayerStatsResponse(
                status="success",
                layer=layer,
                mean=round(float(np.mean(valid)), 4),
                min=round(float(np.min(valid)), 4),
                max=round(float(np.max(valid)), 4),
                std=round(float(np.std(valid)), 4),
                pixel_count=int(len(valid)),
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Layer stats computation failed")
        raise HTTPException(500, f"Layer stats failed: {e}")


# ── Map download ─────────────────────────────────────────────────────────────


def _get_layer_resolver():
    from main import layer_resolver
    return layer_resolver


def _get_settings():
    from main import settings
    return settings


class DownloadRequest(BaseModel):
    layer: str = Field(
        ...,
        description="Layer name (e.g. 'ndvi', 'lst', 'uhi') or 'uhi' for the prediction output.",
    )
    geometry: Optional[dict] = Field(
        None,
        description="Optional GeoJSON Polygon to crop. If null, returns full raster.",
    )


@router.post("/predict/download")
async def download_layer(
    request: DownloadRequest,
    predictor: ZonePredictor = Depends(_get_zone_predictor),
):
    """
    Download a GeoTIFF layer — full extent or cropped to a drawn zone.
    Returns the raw raster file (not decoded, original COG encoding).
    """
    import asyncio
    from algorithm.infrastructure.layer_resolver import LayerResolver
    from algorithm.config import Settings

    resolver: LayerResolver = _get_layer_resolver()
    settings: Settings = _get_settings()

    # Resolve the file path
    if request.layer == "uhi":
        # UHI prediction output
        uhi_path = Path(settings.output_path) / "uhi_xgb_heatmap_brussels_2024.tif"
        if not uhi_path.exists():
            raise HTTPException(404, "UHI prediction output not found. Run full-map prediction first.")
        file_path = uhi_path
    else:
        entity_ids = settings.all_layer_entity_ids
        if request.layer not in entity_ids:
            raise HTTPException(
                422,
                f"Unknown layer '{request.layer}'. Available: {list(entity_ids.keys())}",
            )
        try:
            paths = await resolver.resolve_required({request.layer: entity_ids[request.layer]})
            file_path = paths[request.layer]
        except Exception as e:
            raise HTTPException(503, f"Cannot resolve layer: {e}")

    # If no geometry, stream the full file
    if request.geometry is None:
        filename = f"{request.layer}_full.tif"

        def iter_file():
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    yield chunk

        return StreamingResponse(
            iter_file(),
            media_type="image/tiff",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # Crop to geometry bounds
    geom = request.geometry
    if geom.get("type") != "Polygon" or not geom.get("coordinates"):
        raise HTTPException(422, "geometry must be a GeoJSON Polygon")

    def crop_to_geotiff():
        coords = np.array(geom["coordinates"][0])
        min_lon, min_lat = coords.min(axis=0)
        max_lon, max_lat = coords.max(axis=0)

        with rasterio.open(file_path) as src:
            # Transform bounds to raster CRS
            if str(src.crs) != "EPSG:4326":
                left, bottom, right, top = transform_bounds(
                    "EPSG:4326", src.crs, min_lon, min_lat, max_lon, max_lat
                )
            else:
                left, bottom, right, top = min_lon, min_lat, max_lon, max_lat

            window = from_bounds(left, bottom, right, top, src.transform)
            window = window.intersection(
                rasterio.windows.Window(0, 0, src.width, src.height)
            )

            data = src.read(window=window)
            win_transform = src.window_transform(window)

            profile = src.profile.copy()
            profile.update(
                width=int(window.width),
                height=int(window.height),
                transform=win_transform,
                compress="deflate",
                tiled=True,
                blockxsize=min(256, int(window.width)),
                blockysize=min(256, int(window.height)),
            )

            buf = io.BytesIO()
            with rasterio.open(buf, "w", **profile) as dst:
                dst.write(data)
                dst.update_tags(**src.tags())
            buf.seek(0)
            return buf

    result_buf = await asyncio.to_thread(crop_to_geotiff)
    filename = f"{request.layer}_crop.tif"

    return StreamingResponse(
        result_buf,
        media_type="image/tiff",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
