"""
Generic uint8 COG Processor

Converts a raw float32 GeoTIFF to a Cloud-Optimized GeoTIFF with uint8 normalization:
- Two-pass processing: first pass finds min/max, second pass normalizes to [0-254]
- 255 reserved for nodata
- VALUE_MIN / VALUE_MAX metadata tags for decoding back to physical values
- DEFLATE compression with horizontal predictor
- 512x512 internal tiles
- Internal overviews (pyramids)

Used for layers like DSM, Imperviousness, Albedo, NDBI.
"""

import logging
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.windows import Window

from processors.cog import build_overviews, create_cog_profile

# Default CRS for Brussels rasters that have no CRS embedded
DEFAULT_CRS = CRS.from_epsg(31370)

logger = logging.getLogger(__name__)

TILE_SIZE = 2048


def process_float32_cog(
    input_path: str,
    output_path: str,
    tile_size: int = TILE_SIZE,
) -> str:
    """
    Convert a raw float32 GeoTIFF to a uint8 COG with normalization and overviews.

    Values are scaled from [min_val, max_val] → [0, 254], with 255 = nodata.
    The original range is stored as VALUE_MIN / VALUE_MAX metadata tags so
    that the LayerDecoder can reconstruct physical values.

    Args:
        input_path:  Path to the source GeoTIFF
        output_path: Path for the COG output
        tile_size:   Processing tile size

    Returns:
        output_path
    """
    logger.info(f"Converting to uint8 COG: {input_path} → {output_path}")
    NODATA_OUT = 255

    with rasterio.open(input_path) as src:
        src_nodata = src.nodata
        height = src.height
        width = src.width

        # ── First pass: find global min / max ─────────────────────────
        valid_chunks = []
        for row_off in range(0, height, tile_size):
            for col_off in range(0, width, tile_size):
                win_h = min(tile_size, height - row_off)
                win_w = min(tile_size, width - col_off)
                window = Window(col_off, row_off, win_w, win_h)

                data = src.read(1, window=window).astype(np.float32)

                if src_nodata is not None:
                    mask = (data != src_nodata) & np.isfinite(data)
                else:
                    mask = np.isfinite(data)

                if mask.any():
                    valid_chunks.append(data[mask])

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

        # ── Second pass: normalize [0-254] and write ──────────────────
        profile = create_cog_profile(src.profile, dtype="uint8")
        profile["nodata"] = NODATA_OUT

        # Assign CRS if missing (common for derived Brussels rasters)
        if profile.get("crs") is None:
            logger.warning(f"  Source has no CRS — assigning {DEFAULT_CRS}")
            profile["crs"] = DEFAULT_CRS

        with rasterio.open(output_path, "w", **profile) as dst:
            for row_off in range(0, height, tile_size):
                for col_off in range(0, width, tile_size):
                    win_h = min(tile_size, height - row_off)
                    win_w = min(tile_size, width - col_off)
                    window = Window(col_off, row_off, win_w, win_h)

                    data = src.read(1, window=window).astype(np.float32)

                    if src_nodata is not None:
                        valid_mask = (data != src_nodata) & np.isfinite(data)
                    else:
                        valid_mask = np.isfinite(data)

                    normalized = np.full(data.shape, NODATA_OUT, dtype=np.uint8)
                    if valid_mask.any():
                        normalized[valid_mask] = np.clip(
                            ((data[valid_mask] - min_val) / (max_val - min_val)) * 254,
                            0,
                            254,
                        ).astype(np.uint8)

                    dst.write(normalized, 1, window=window)

            dst.update_tags(
                SOURCE=str(input_path),
                VALUE_MIN=str(min_val),
                VALUE_MAX=str(max_val),
            )

    build_overviews(output_path, resampling=Resampling.average)
    logger.info(f"uint8 COG saved: {output_path}")
    return output_path
