"""
UHI Raster Engine — pure domain logic for NDVI→heat-risk conversion.

Encoding contract (stable across versions):
  - Output dtype  : uint8
  - Value [0,254] : heat-risk [0.0, 1.0]  (0=cool, 1=hot)
  - Value 255     : nodata
  - Decode        : heat_risk = pixel / 254
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import Window

logger = logging.getLogger(__name__)

TILE_SIZE = 2048
OVERVIEW_FACTORS = [2, 4, 8, 16, 32]
COG_BLOCKSIZE = 512


class UHIRasterEngine:
    """
    Generates a COG-optimised heat-risk GeoTIFF from an NDVI raster.

    Both algorithms share the same output encoding contract above.
    """

    def generate(self, ndvi_path: Path, output_path: Path) -> Path:
        """
        Run the full pipeline: read NDVI → compute heat risk → write COG.

        Parameters
        ----------
        ndvi_path   : Path to input NDVI GeoTIFF
        output_path : Destination path for the output GeoTIFF

        Returns
        -------
        output_path (same value, for chaining convenience)
        """
        logger.info(f"Generating heat-risk raster: {ndvi_path} → {output_path}")

        with rasterio.open(ndvi_path) as src:
            profile = self._build_cog_profile(src)
            self._write_tiles(src, output_path, profile)

        self._build_overviews(output_path)
        logger.info(f"Heat-risk raster saved: {output_path}")
        return output_path

    # ── Private helpers ───────────────────────────────────────────────

    def _build_cog_profile(self, src: rasterio.DatasetReader) -> dict:
        """Build the output rasterio profile for a uint8 COG GeoTIFF."""
        profile = src.profile.copy()
        profile.update(
            driver="GTiff",
            dtype="uint8",
            count=1,
            nodata=255,
            compress="deflate",
            predictor=2,
            tiled=True,
            blockxsize=COG_BLOCKSIZE,
            blockysize=COG_BLOCKSIZE,
        )
        # photometric tag is incompatible with single-band uint8 in some readers
        profile.pop("photometric", None)
        return profile

    def _write_tiles(
        self,
        src: rasterio.DatasetReader,
        output_path: Path,
        profile: dict,
    ) -> None:
        """Iterate over tiles, compute heat risk, write each tile."""
        height, width = src.height, src.width
        input_dtype = src.dtypes[0]
        input_nodata = src.nodata
        total_tiles = self._count_tiles(height, width)
        tile_count = 0

        with rasterio.open(output_path, "w", **profile) as dst:
            for row_off in range(0, height, TILE_SIZE):
                for col_off in range(0, width, TILE_SIZE):
                    window = Window(
                        col_off, row_off,
                        min(TILE_SIZE, width - col_off),
                        min(TILE_SIZE, height - row_off),
                    )
                    ndvi_raw = src.read(1, window=window)
                    ndvi, nodata_mask = self._decode_ndvi(
                        ndvi_raw, input_dtype, input_nodata
                    )
                    heat_uint8 = self._ndvi_to_heat_uint8(ndvi, nodata_mask)
                    dst.write(heat_uint8, 1, window=window)

                    tile_count += 1
                    if tile_count % 100 == 0:
                        logger.info(f"  Progress: {tile_count}/{total_tiles} tiles")

            dst.update_tags(**self._output_metadata())

    @staticmethod
    def _decode_ndvi(
        raw: np.ndarray,
        dtype: str,
        nodata_value,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Decode raw pixel values to float32 NDVI in [-1, 1].

        Returns (ndvi_float32, nodata_boolean_mask).

        Two cases:
          - uint8 input : values [0,254] → NDVI [-1,1], value 255 = nodata
          - float input : passed through as-is, nodata from rasterio profile
        """
        if dtype == "uint8":
            nodata_mask = raw == 255
            ndvi = (raw.astype(np.float32) / 254.0) * 2.0 - 1.0
        else:
            nodata_mask = (
                raw == nodata_value
                if nodata_value is not None
                else np.zeros_like(raw, dtype=bool)
            )
            ndvi = raw.astype(np.float32)

        return ndvi, nodata_mask

    @staticmethod
    def _ndvi_to_heat_uint8(
        ndvi: np.ndarray,
        nodata_mask: np.ndarray,
    ) -> np.ndarray:
        """
        Convert float32 NDVI to uint8 heat-risk.

        Formula: heat_risk = 1 - (ndvi + 1) / 2
        Rationale: dense vegetation (NDVI≈1) → low heat risk (0).
                   bare soil / urban (NDVI≈-1) → high heat risk (1).
        """
        heat_risk = np.clip(1.0 - (ndvi + 1.0) / 2.0, 0.0, 1.0)
        result = (heat_risk * 254.0).astype(np.uint8)
        result[nodata_mask] = 255
        return result

    @staticmethod
    def _count_tiles(height: int, width: int) -> int:
        return (
            ((height + TILE_SIZE - 1) // TILE_SIZE)
            * ((width + TILE_SIZE - 1) // TILE_SIZE)
        )

    @staticmethod
    def _build_overviews(path: Path) -> None:
        logger.info("Building overviews…")
        with rasterio.open(path, "r+") as ds:
            ds.build_overviews(OVERVIEW_FACTORS, Resampling.average)
            ds.update_tags(ns="rio_overview", resampling="average")

    @staticmethod
    def _output_metadata() -> dict:
        return {
            "LAYER_TYPE": "UHI_PREDICTION",
            "MODEL_VERSION": "placeholder_v1",
            "INPUT_LAYERS": "NDVI",
            "FORMULA": "heat_risk = 1 - (ndvi + 1) / 2",
            "VALUE_RANGE": "0 to 1 (0=cool, 1=hot)",
            "ENCODING": "uint8: [0,254]→[0,1], 255=nodata",
            "DECODE_FORMULA": "heat_risk = pixel / 254",
            "GENERATED_AT": datetime.now(timezone.utc).isoformat(),
        }