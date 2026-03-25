"""
NDWI (Normalized Difference Water Index) Processor

NDWI = (Green - NIR) / (Green + NIR)

Interpretation:
  [ 0.2,  1.0] : Open water (rivers, lakes, ponds)
  [-0.1,  0.2] : Flooded or saturated surfaces
  [-1.0, -0.1] : Vegetation, soil, built-up areas (non-water)

Output is a Cloud-Optimized GeoTIFF (COG) with:
  - uint8 encoding: [-1, 1] → [0, 254], 255 = nodata
  - DEFLATE compression, 512×512 internal tiles
  - Multi-level overviews (2×, 4×, 8×, 16×, 32×)

Uses tiled (windowed) processing to handle files larger than available RAM.
To decode: ndwi = (pixel / 254) * 2 - 1
"""

import logging

import numpy as np
import rasterio
from rasterio.enums import Resampling

from processors.cog import build_overviews, create_cog_profile
from processors.utils import detect_nodata_mask, iter_windows, normalized_difference

logger = logging.getLogger(__name__)

TILE_SIZE = 2048
NODATA_VALUE = 255


def calculate_ndwi(
    rgb_path: str,
    nir_path: str,
    output_path: str,
    green_band_index: int = 2,
    tile_size: int = TILE_SIZE,
    nodata_values: tuple = (254, 255),
) -> str:
    """
    Calculate NDWI from RGB and NIR orthophotos using tiled processing.

    Args:
        rgb_path:         Path to RGB GeoTIFF
        nir_path:         Path to NIR GeoTIFF
        output_path:      Path for the NDWI output GeoTIFF
        green_band_index: Green band index in the RGB file (1-indexed, default 2)
        tile_size:        Processing tile size in pixels (default 2048)
        nodata_values:    Pixel values treated as nodata in source images

    Returns:
        output_path
    """
    logger.info(f"Calculating NDWI: {rgb_path} + {nir_path} -> {output_path}")

    with rasterio.open(rgb_path) as rgb_src, rasterio.open(nir_path) as nir_src:
        height = min(rgb_src.height, nir_src.height)
        width = min(rgb_src.width, nir_src.width)
        logger.info(f"Output dimensions: {width} x {height}")

        profile = create_cog_profile(rgb_src.profile.copy(), dtype="uint8")
        profile.update(height=height, width=width)

        windows = list(iter_windows(height, width, tile_size))

        with rasterio.open(output_path, "w", **profile) as dst:
            for i, window in enumerate(windows):
                # A pixel is nodata if either the RGB or NIR source has nodata there
                nodata_mask = (
                    detect_nodata_mask(rgb_src, window, nodata_values)
                    | detect_nodata_mask(nir_src, window, nodata_values)
                )

                green = rgb_src.read(green_band_index, window=window).astype(np.float32)
                nir = nir_src.read(1, window=window).astype(np.float32)

                # NDWI = (Green - NIR) / (Green + NIR), clipped to [-1, 1]
                ndwi = normalized_difference(green, nir)

                # Encode [-1, 1] → [0, 254]; mark nodata pixels as 255
                ndwi_uint8 = ((ndwi + 1) / 2 * 254).astype(np.uint8)
                ndwi_uint8[nodata_mask] = NODATA_VALUE

                dst.write(ndwi_uint8, 1, window=window)

                if (i + 1) % 100 == 0:
                    logger.info(f"NDWI progress: {i + 1}/{len(windows)} tiles")

            dst.update_tags(
                LAYER_TYPE="NDWI",
                FORMULA="(Green - NIR) / (Green + NIR)",
                VALUE_RANGE="-1 to 1",
                ENCODING="uint8 [0,254] = [-1,1], 255 = nodata",
                DECODE_FORMULA="ndwi = (pixel / 254) * 2 - 1",
            )

    build_overviews(output_path, resampling=Resampling.average)
    logger.info(f"NDWI saved: {output_path}")
    return output_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4:
        calculate_ndwi(sys.argv[1], sys.argv[2], sys.argv[3])
    else:
        print("Usage: python ndwi.py <rgb_path> <nir_path> <output_path>")
