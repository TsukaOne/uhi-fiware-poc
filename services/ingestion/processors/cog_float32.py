"""
Generic float32 → uint8 COG Processor

Converts any raw float32 GeoTIFF to a Cloud-Optimized GeoTIFF with uint8 encoding:
- Two-pass processing: first pass finds the global min/max, second pass normalizes
- Encoding: [min, max] → [0, 254], 255 reserved for nodata
- VALUE_MIN / VALUE_MAX stored as metadata tags for client-side decoding
- DEFLATE compression, 512×512 internal tiles, multi-level overviews

Used for DSM, NDBI, Imperviousness, Albedo, DTM, LST and any other continuous
float32 layer that needs COG conversion.
"""

import logging
from typing import Optional

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling

from processors.cog import build_overviews, create_cog_profile
from processors.utils import iter_windows

# Fallback CRS for Brussels-derived rasters that have no CRS embedded
DEFAULT_CRS = CRS.from_epsg(31370)

NODATA_OUT = 255
TILE_SIZE = 2048

logger = logging.getLogger(__name__)


def process_float32_cog(
    input_path: str,
    output_path: str,
    tile_size: int = TILE_SIZE,
    extra_tags: Optional[dict] = None,
) -> str:
    """
    Convert a raw float32 GeoTIFF to a uint8 COG with global normalization.

    Pass 1 — scan all tiles to find the global value range [min, max].
    Pass 2 — normalize each pixel to [0, 254] and write the COG.

    The original range is stored as VALUE_MIN / VALUE_MAX metadata tags so
    that consumers can reconstruct physical values:
        physical_value = VALUE_MIN + (pixel / 254) * (VALUE_MAX - VALUE_MIN)

    Args:
        input_path:  Path to the source float32 GeoTIFF
        output_path: Path for the uint8 COG output
        tile_size:   Processing tile size in pixels (default 2048)
        extra_tags:  Additional metadata tags to write alongside VALUE_MIN/MAX

    Returns:
        output_path

    Raises:
        ValueError: If the source file contains no valid (non-nodata) pixels
    """
    logger.info(f"Converting to uint8 COG: {input_path} -> {output_path}")

    with rasterio.open(input_path) as src:
        src_nodata = src.nodata
        height, width = src.height, src.width

        # ── Pass 1: find global min / max across all tiles ─────────────────────
        valid_chunks = []
        for window in iter_windows(height, width, tile_size):
            data = src.read(1, window=window).astype(np.float32)
            valid_mask = (data != src_nodata) & np.isfinite(data) if src_nodata is not None else np.isfinite(data)
            if valid_mask.any():
                valid_chunks.append(data[valid_mask])

        if not valid_chunks:
            raise ValueError(
                f"No valid (non-nodata) pixels found in {input_path}. "
                "Check that the file contains actual data."
            )

        all_valid = np.concatenate(valid_chunks)
        min_val = float(np.min(all_valid))
        max_val = float(np.max(all_valid))
        del all_valid, valid_chunks

        logger.info(f"  Value range: [{min_val:.4f}, {max_val:.4f}]")

        # ── Pass 2: normalize [min, max] → [0, 254] and write COG ─────────────
        profile = create_cog_profile(src.profile, dtype="uint8")
        profile["nodata"] = NODATA_OUT

        if profile.get("crs") is None:
            logger.warning(f"  No CRS in source — assigning {DEFAULT_CRS}")
            profile["crs"] = DEFAULT_CRS

        with rasterio.open(output_path, "w", **profile) as dst:
            for window in iter_windows(height, width, tile_size):
                data = src.read(1, window=window).astype(np.float32)
                valid_mask = (data != src_nodata) & np.isfinite(data) if src_nodata is not None else np.isfinite(data)

                normalized = np.full(data.shape, NODATA_OUT, dtype=np.uint8)
                if valid_mask.any():
                    normalized[valid_mask] = np.clip(
                        ((data[valid_mask] - min_val) / (max_val - min_val)) * 254,
                        0,
                        254,
                    ).astype(np.uint8)

                dst.write(normalized, 1, window=window)

            tags = {"SOURCE": str(input_path), "VALUE_MIN": str(min_val), "VALUE_MAX": str(max_val)}
            if extra_tags:
                tags.update(extra_tags)
            dst.update_tags(**tags)

    build_overviews(output_path, resampling=Resampling.average)
    logger.info(f"uint8 COG saved: {output_path}")
    return output_path
