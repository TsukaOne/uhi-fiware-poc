"""
Zone Predictor — XGBoost inference restricted to a user-drawn polygon/bbox.

Pipeline:
  1. Convert GeoJSON geometry → pixel window on the reference grid
  2. Read only the bounding window from all 10 input layers
  3. Rasterize the polygon to a pixel mask inside that window
  4. Apply object impacts (trees, buildings, …) to the feature rasters
  5. Run XGBoost.predict() on valid pixels inside the mask
  6. Encode result as RGBA PNG with the UHI colormap
  7. Return PNG bytes + geographic bounds + statistics

Returns a lightweight PNG (no COG, no disk, no GeoServer) for
immediate overlay in Cesium via SingleTileImageryProvider.
"""
from __future__ import annotations

import io
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import rowcol
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import Window, from_bounds
from scipy.ndimage import distance_transform_edt
from PIL import Image

from algorithm.domain.layer_decoder import LayerDecoder

logger = logging.getLogger(__name__)

# ── Object impact definitions ─────────────────────────────────────────────────
# Each object type maps to {feature_name: delta_value}.
# Deltas are applied to the *decoded* physical values.

@dataclass(frozen=True)
class ObjectImpact:
    deltas: dict[str, float]
    radius_m: float

OBJECT_IMPACTS: dict[str, ObjectImpact] = {
    "tree_deciduous": ObjectImpact(
        deltas={"ndvi": +0.6, "imperviousness": -0.5, "albedo": +0.05, "dsm": +12.0},
        radius_m=5.0,
    ),
    "tree_conifer": ObjectImpact(
        deltas={"ndvi": +0.5, "imperviousness": -0.5, "albedo": +0.03, "dsm": +10.0},
        radius_m=4.0,
    ),
    "shrub": ObjectImpact(
        deltas={"ndvi": +0.3, "imperviousness": -0.3, "albedo": +0.03, "dsm": +3.0},
        radius_m=3.0,
    ),
    "grass": ObjectImpact(
        deltas={"ndvi": +0.2, "imperviousness": -0.4, "albedo": +0.02},
        radius_m=4.0,
    ),
    "building_residential": ObjectImpact(
        deltas={"ndvi": -0.3, "imperviousness": +0.8, "albedo": -0.1,
                "building_height": +10.0, "dsm": +10.0},
        radius_m=8.0,
    ),
    "building_commercial": ObjectImpact(
        deltas={"ndvi": -0.3, "imperviousness": +0.9, "albedo": -0.15,
                "building_height": +20.0, "dsm": +20.0},
        radius_m=12.0,
    ),
    "building_industrial": ObjectImpact(
        deltas={"ndvi": -0.4, "imperviousness": +0.95, "albedo": -0.2,
                "building_height": +15.0, "dsm": +15.0},
        radius_m=15.0,
    ),
    "water_fountain": ObjectImpact(
        deltas={"ndwi": +0.5, "imperviousness": -0.3, "albedo": +0.1},
        radius_m=3.0,
    ),
    "park_bench": ObjectImpact(
        deltas={},
        radius_m=1.0,
    ),
    "solar_panel": ObjectImpact(
        deltas={"imperviousness": +0.2, "albedo": -0.3},
        radius_m=3.0,
    ),
}

# ── UHI colormap (matches GeoServer SLD: RdYlBu on normalized [0,1]) ─────────
# Breakpoints correspond to GeoServer SLD uint8 quantities / 254.
UHI_NORMALIZED_COLORS = [
    (0   / 254, (49,  54,  149, 255)),   # #313695 — Very Cold
    (50  / 254, (69,  117, 180, 255)),   # #4575b4
    (90  / 254, (116, 173, 209, 255)),   # #74add1
    (110 / 254, (171, 217, 233, 255)),   # #abd9e9
    (127 / 254, (255, 255, 191, 255)),   # #ffffbf — Neutral
    (160 / 254, (253, 174, 97,  255)),   # #fdae61
    (190 / 254, (244, 109, 67,  255)),   # #f46d43
    (220 / 254, (215, 48,  39,  255)),   # #d73027
    (254 / 254, (165, 0,   38,  255)),   # #a50026 — Very Hot
]

#Results dataclasses
@dataclass
class ZonePredictionResult:
    png_bytes: bytes
    bounds: dict  # {west, south, east, north} in WGS84
    stats: dict   # {mean_uhi, min_uhi, max_uhi, pixel_count, duration_ms}

# Stats dataclass for decoded layer values within the zone
@dataclass
class ZoneStatsResult:
    layer_stats: dict[str, dict]  # {layer_name: {mean, min, max, std}}
    pixel_count: int
    bounds: dict

#
@dataclass
class PixelValueResult:
    values: dict[str, float | None]  # {layer_name: decoded_value or None}
    lon: float
    lat: float


class ZonePredictor:
    """
    Predicts UHI intensity for a user-drawn zone.
    """

    def __init__(self, model_path: Path, layer_resolver, settings) -> None:
        self._model_path = model_path #Path to the model
        self._resolver = layer_resolver # LayerResolver instance
        self._settings = settings # Setttings instance
        self._decoder = LayerDecoder()# LayerDecoder instance for decoding raw raster values 


    async def predict(self,geometry: dict, objects: list[dict],) -> ZonePredictionResult:
        """
        Run zone prediction. Called from the async endpoint but
        heavy computation runs in threads via asyncio.to_thread.

        Parameters
        ----------
        geometry : GeoJSON-like dict with 'type' and 'coordinates'
        objects  : list of {type: str, lon: float, lat: float}
        """
        import asyncio
        import time

        # Timer for performance logging
        t0 = time.perf_counter()

        # 1. Resolve all layer paths from Orion
        paths = await self._resolver.resolve_required(
            self._settings.all_layer_entity_ids
        )

        # 2. Threaded prediction to avoid blocking the event Loop
        result = await asyncio.to_thread(
            self._predict_sync, geometry, objects, paths
        )

        # Log performance stats
        duration_ms = (time.perf_counter() - t0) * 1000
        result.stats["duration_ms"] = round(duration_ms, 1)
        logger.info(
            f"Zone prediction done: {result.stats['pixel_count']} pixels "
            f"in {duration_ms:.0f}ms"
        )
        return result

    # ── Synchronous prediction (runs in thread) ──────────────────────────
    def _predict_sync(self, geometry: dict, objects: list[dict], paths: dict[str, Path],) -> ZonePredictionResult:
        # 1. Load model
        model_file = self._model_path / "xgb_uhi_latest.joblib"
        if not model_file.exists():
            raise FileNotFoundError(
                f"No trained model at {model_file}. Run POST /training/start first."
            )
        artifact = joblib.load(model_file)
        xgb_model = artifact["model"]
        xgb_model.set_params(nthread=os.cpu_count())
        uhi_min = float(artifact.get("uhi_min", 0.0))
        uhi_max = float(artifact.get("uhi_max", 1.0))

        # 2. Compute pixel window from geometry
        ndvi_path = paths["ndvi"]
        with rasterio.open(ndvi_path) as ref:
            ref_crs = ref.crs
            ref_transform = ref.transform
            total_h, total_w = ref.height, ref.width
            pixel_size = abs(ref_transform.a)

        window, poly_mask = self._geometry_to_window_and_mask(
            geometry, ref_crs, ref_transform, total_h, total_w
        )

        win_h, win_w = window.height, window.width
        logger.info(f"Zone window: {win_w}x{win_h} px (offset: {window.col_off}, {window.row_off})")

        # 3. Read all layers for this window (parallel I/O)
        decoded_layers = self._read_layers_parallel(
            paths, window, ref_transform, ref_crs
        )

        # 4. Apply object impacts
        if objects:
            self._apply_object_impacts(
                decoded_layers, objects, window, ref_transform, ref_crs, pixel_size
            )

        # 5. Build validity mask
        valid = poly_mask.copy()
        for name, (decoded, nodata_mask) in decoded_layers.items():
            valid &= ~nodata_mask

        lst_f, _ = decoded_layers.get("lst", (np.zeros((win_h, win_w)), np.ones((win_h, win_w), dtype=bool)))
        valid &= np.isfinite(lst_f) & (lst_f > 0)

        n_valid = int(valid.sum())
        if n_valid == 0:
            # No valid pixels — return transparent PNG
            bounds_wgs84 = self._window_bounds_wgs84(window, ref_transform, ref_crs)
            empty_png = self._make_transparent_png(win_w, win_h)
            return ZonePredictionResult(
                png_bytes=empty_png,
                bounds=bounds_wgs84,
                stats={"mean_uhi": 0, "min_uhi": 0, "max_uhi": 0, "pixel_count": 0},
            )

        # 6. Pre-compute distance features for this window
        dist_water, dist_park = self._compute_local_distances(
            decoded_layers, pixel_size
        )

        # 7. Build feature matrix
        idx = np.flatnonzero(valid)
        rr, cc = np.unravel_index(idx, (win_h, win_w))

        X = np.column_stack([
            decoded_layers["ndvi"][0].ravel()[idx],
            decoded_layers["ndwi"][0].ravel()[idx],
            decoded_layers["ndbi"][0].ravel()[idx],
            decoded_layers["dtm"][0].ravel()[idx],
            decoded_layers["dsm"][0].ravel()[idx],
            decoded_layers["building_height"][0].ravel()[idx],
            decoded_layers["imperviousness"][0].ravel()[idx],
            decoded_layers["albedo"][0].ravel()[idx],
            dist_water.ravel()[idx],
            dist_park.ravel()[idx],
        ]).astype(np.float32)

        # 8. XGBoost inference
        y_pred = xgb_model.predict(X).astype(np.float32)

        # 9. Build UHI raster
        uhi_raster = np.full((win_h, win_w), np.nan, dtype=np.float32)
        uhi_raster[rr, cc] = y_pred

        stats = {
            "mean_uhi": round(float(np.nanmean(y_pred)), 3),
            "min_uhi": round(float(np.nanmin(y_pred)), 3),
            "max_uhi": round(float(np.nanmax(y_pred)), 3),
            "pixel_count": n_valid,
            "uhi_range": {"min": round(uhi_min, 3), "max": round(uhi_max, 3)},
            "image_width": win_w,
            "image_height": win_h,
        }

        # 10. Encode as RGBA PNG with colormap (same scale as GeoServer WMS)
        png_bytes = self._uhi_to_png(uhi_raster, valid, uhi_min, uhi_max)
        bounds_wgs84 = self._window_bounds_wgs84(window, ref_transform, ref_crs)

        return ZonePredictionResult(
            png_bytes=png_bytes,
            bounds=bounds_wgs84,
            stats=stats,
        )

    # ── Geometry → pixel window + mask ───────────────────────────────────

    def _geometry_to_window_and_mask(
        self,
        geometry: dict,
        ref_crs,
        ref_transform,
        total_h: int,
        total_w: int,
    ) -> tuple[Window, np.ndarray]:
        """
        Convert a GeoJSON polygon (WGS84) to a rasterio Window
        and a boolean mask (True = inside polygon).
        """
        from rasterio.features import geometry_mask
        from rasterio.warp import transform_geom

        # Reproject geometry from WGS84 to raster CRS
        geom_native = transform_geom("EPSG:4326", ref_crs, geometry)

        # Get bounding window
        coords = np.array(geom_native["coordinates"][0])
        min_x, min_y = coords.min(axis=0)
        max_x, max_y = coords.max(axis=0)

        # Clamp to raster extent
        win = from_bounds(min_x, min_y, max_x, max_y, ref_transform)
        col_off = max(0, int(win.col_off))
        row_off = max(0, int(win.row_off))
        col_end = min(total_w, int(win.col_off + win.width))
        row_end = min(total_h, int(win.row_off + win.height))
        window = Window(col_off, row_off, col_end - col_off, row_end - row_off)

        # Build pixel mask for the polygon within this window
        win_transform = rasterio.windows.transform(window, ref_transform)
        mask = geometry_mask(
            [geom_native],
            out_shape=(window.height, window.width),
            transform=win_transform,
            invert=True,  # True inside polygon
        )
        return window, mask

    # ── Parallel layer reading ───────────────────────────────────────────

    def _read_layers_parallel(
        self,
        paths: dict[str, Path],
        window: Window,
        ref_transform,
        ref_crs,
    ) -> dict[str, tuple[np.ndarray, np.ndarray]]:
        native = {"ndvi", "ndwi", "ndbi"}

        def _load(name: str, path: Path):
            if name in native:
                with rasterio.open(path) as src:
                    raw = src.read(
                        1, window=window, boundless=True,
                        fill_value=src.nodata if src.nodata is not None else 0,
                        out_dtype=np.float32,
                    )
                decoded, nodata_mask = self._decoder.decode(
                    raw=raw, layer_name=name, raster_path=str(path),
                )
                return name, (decoded, nodata_mask)

            # Reproject to reference window extent
            h, w = window.height, window.width
            raw = np.full((h, w), np.nan, dtype=np.float32)
            bounds = rasterio.windows.bounds(window, ref_transform)
            dst_tf = rasterio.transform.from_bounds(*bounds, width=w, height=h)
            with rasterio.open(path) as src:
                reproject(
                    source=rasterio.band(src, 1),
                    destination=raw,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    src_nodata=src.nodata,
                    dst_transform=dst_tf,
                    dst_crs=ref_crs,
                    dst_nodata=np.nan,
                    resampling=Resampling.bilinear,
                )
            decoded, nodata_mask = self._decoder.decode(
                raw=raw, layer_name=name, raster_path=str(path),
            )
            return name, (decoded, nodata_mask)

        results = {}
        with ThreadPoolExecutor(max_workers=min(len(paths), 6)) as pool:
            for name, result in pool.map(lambda kv: _load(*kv), paths.items()):
                results[name] = result
        return results

    # ── Object impact application ────────────────────────────────────────

    def _apply_object_impacts(
        self,
        decoded_layers: dict[str, tuple[np.ndarray, np.ndarray]],
        objects: list[dict],
        window: Window,
        ref_transform,
        ref_crs,
        pixel_size: float,
    ) -> None:
        """Modify decoded feature arrays in-place based on placed objects."""
        from rasterio.warp import transform as transform_coords

        win_transform = rasterio.windows.transform(window, ref_transform)
        h, w = window.height, window.width

        for obj in objects:
            obj_type = obj.get("type", "")
            impact = OBJECT_IMPACTS.get(obj_type)
            if impact is None:
                logger.warning(f"Unknown object type '{obj_type}' — skipping")
                continue

            lon, lat = obj.get("lon"), obj.get("lat")
            if lon is None or lat is None:
                continue

            # Convert lon/lat to pixel coordinates within the window
            xs, ys = transform_coords("EPSG:4326", ref_crs, [lon], [lat])
            try:
                row, col = rowcol(win_transform, xs[0], ys[0])
            except Exception:
                continue

            # Compute footprint circle in pixels
            radius_px = max(1, int(impact.radius_m / pixel_size))

            # Build circular mask
            rr, cc = np.ogrid[
                max(0, row - radius_px):min(h, row + radius_px + 1),
                max(0, col - radius_px):min(w, col + radius_px + 1),
            ]
            # Distances from center
            dr = rr - row
            dc = cc - col
            circle = (dr * dr + dc * dc) <= (radius_px * radius_px)

            r_start = max(0, row - radius_px)
            c_start = max(0, col - radius_px)

            # Apply deltas to each affected feature
            for feature_name, delta in impact.deltas.items():
                if feature_name not in decoded_layers:
                    continue
                arr, nodata = decoded_layers[feature_name]
                sub = arr[r_start:r_start + circle.shape[0],
                          c_start:c_start + circle.shape[1]]
                sub[circle] += delta

    # ── Local distance computation ───────────────────────────────────────

    def _compute_local_distances(
        self,
        decoded_layers: dict[str, tuple[np.ndarray, np.ndarray]],
        pixel_size: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Compute distance-to-water and distance-to-park for the zone window.
        Works directly on the already-decoded arrays (no disk I/O).
        """
        ndwi_data, _ = decoded_layers["ndwi"]
        water_mask = ndwi_data > 0.0
        dist_water = distance_transform_edt(~water_mask).astype(np.float32)
        dist_water *= pixel_size

        ndvi_data, _ = decoded_layers["ndvi"]
        park_mask = ndvi_data > 0.4
        dist_park = distance_transform_edt(~park_mask).astype(np.float32)
        dist_park *= pixel_size

        return dist_water, dist_park

    # ── UHI → RGBA PNG ───────────────────────────────────────────────────

    def _uhi_to_png(
        self,
        uhi_raster: np.ndarray,
        valid_mask: np.ndarray,
        uhi_min: float,
        uhi_max: float,
    ) -> bytes:
        """
        Convert UHI raster (°C delta) to RGBA PNG using the same colormap
        as the GeoServer SLD for visual consistency.

        Encoding matches predict_service: heat_risk = (y_pred - uhi_min) / (uhi_max - uhi_min)
        then the RdYlBu ramp is applied on the [0, 1] normalized range.
        """
        h, w = uhi_raster.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)

        # Normalize exactly like the full-map COG encoding
        uhi_range = uhi_max - uhi_min
        if uhi_range <= 0:
            uhi_range = 1.0
        normalized = (uhi_raster - uhi_min) / uhi_range
        normalized = np.clip(normalized, 0.0, 1.0)

        breakpoints = np.array([b for b, _ in UHI_NORMALIZED_COLORS], dtype=np.float32)
        colors = np.array([c for _, c in UHI_NORMALIZED_COLORS], dtype=np.float32)

        for i in range(4):  # R, G, B, A
            rgba[:, :, i] = np.where(
                valid_mask,
                np.interp(normalized, breakpoints, colors[:, i]).astype(np.uint8),
                0,
            )

        img = Image.fromarray(rgba, "RGBA")
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _window_bounds_wgs84(window, ref_transform, ref_crs) -> dict:
        bounds = rasterio.windows.bounds(window, ref_transform)
        west, south, east, north = transform_bounds(ref_crs, "EPSG:4326", *bounds)
        return {"west": west, "south": south, "east": east, "north": north}

    @staticmethod
    def _make_transparent_png(width: int, height: int) -> bytes:
        img = Image.fromarray(
            np.zeros((height, width, 4), dtype=np.uint8), "RGBA"
        )
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    # ── Zone statistics (decoded layer values) ───────────────────────

    async def compute_zone_stats(self, geometry: dict) -> ZoneStatsResult:
        """Compute mean/min/max/std of all decoded layers within a zone."""
        import asyncio

        paths = await self._resolver.resolve_required(
            self._settings.all_layer_entity_ids
        )
        return await asyncio.to_thread(
            self._compute_zone_stats_sync, geometry, paths
        )

    def _compute_zone_stats_sync(
        self, geometry: dict, paths: dict[str, Path]
    ) -> ZoneStatsResult:
        ndvi_path = paths["ndvi"]
        with rasterio.open(ndvi_path) as ref:
            ref_crs = ref.crs
            ref_transform = ref.transform
            total_h, total_w = ref.height, ref.width
            pixel_size = abs(ref_transform.a)

        window, poly_mask = self._geometry_to_window_and_mask(
            geometry, ref_crs, ref_transform, total_h, total_w
        )

        decoded_layers = self._read_layers_parallel(
            paths, window, ref_transform, ref_crs
        )

        # Build validity mask
        valid = poly_mask.copy()
        for name, (decoded, nodata_mask) in decoded_layers.items():
            valid &= ~nodata_mask

        n_valid = int(valid.sum())
        if n_valid == 0:
            bounds = self._window_bounds_wgs84(window, ref_transform, ref_crs)
            return ZoneStatsResult(layer_stats={}, pixel_count=0, bounds=bounds)

        # Compute distance features
        dist_water, dist_park = self._compute_local_distances(
            decoded_layers, pixel_size
        )

        # Stats for each layer + distance features
        layer_stats = {}
        for name, (decoded, _) in decoded_layers.items():
            vals = decoded[valid]
            vals = vals[np.isfinite(vals)]
            if len(vals) == 0:
                continue
            layer_stats[name] = {
                "mean": round(float(np.mean(vals)), 4),
                "min": round(float(np.min(vals)), 4),
                "max": round(float(np.max(vals)), 4),
                "std": round(float(np.std(vals)), 4),
            }

        # Distance features
        for feat_name, feat_arr in [("distance_to_water", dist_water), ("distance_to_park", dist_park)]:
            vals = feat_arr[valid]
            vals = vals[np.isfinite(vals)]
            if len(vals) > 0:
                layer_stats[feat_name] = {
                    "mean": round(float(np.mean(vals)), 2),
                    "min": round(float(np.min(vals)), 2),
                    "max": round(float(np.max(vals)), 2),
                    "std": round(float(np.std(vals)), 2),
                }

        bounds = self._window_bounds_wgs84(window, ref_transform, ref_crs)
        return ZoneStatsResult(
            layer_stats=layer_stats, pixel_count=n_valid, bounds=bounds
        )

    # ── Single pixel value lookup ────────────────────────────────────

    async def get_pixel_values(self, lon: float, lat: float) -> PixelValueResult:
        """Return decoded physical values for all layers at a single lon/lat."""
        import asyncio

        paths = await self._resolver.resolve_required(
            self._settings.all_layer_entity_ids
        )
        return await asyncio.to_thread(
            self._get_pixel_values_sync, lon, lat, paths
        )

    def _get_pixel_values_sync(
        self, lon: float, lat: float, paths: dict[str, Path]
    ) -> PixelValueResult:
        from pyproj import Transformer

        values: dict[str, float | None] = {}

        for layer_name, path in paths.items():
            try:
                with rasterio.open(path) as src:
                    # Transform lon/lat to raster CRS
                    if str(src.crs) != "EPSG:4326":
                        transformer = Transformer.from_crs(
                            "EPSG:4326", src.crs, always_xy=True
                        )
                        x, y = transformer.transform(lon, lat)
                    else:
                        x, y = lon, lat

                    row, col = src.index(x, y)

                    # Check bounds
                    if row < 0 or row >= src.height or col < 0 or col >= src.width:
                        values[layer_name] = None
                        continue

                    # Read single pixel
                    window = Window(col, row, 1, 1)
                    raw = src.read(1, window=window)

                    # Decode
                    decoded, nodata_mask = self._decoder.decode(
                        raw, layer_name, raster_path=str(path)
                    )

                    if nodata_mask[0, 0]:
                        values[layer_name] = None
                    else:
                        values[layer_name] = round(float(decoded[0, 0]), 4)

            except Exception as exc:
                logger.warning(f"Failed to read pixel for {layer_name}: {exc}")
                values[layer_name] = None

        return PixelValueResult(values=values, lon=lon, lat=lat)
