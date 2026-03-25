"""
DTM (Digital Terrain Model) Processor

Converts a raw DTM GeoTIFF (float32, elevation in metres) to a uint8
Cloud-Optimized GeoTIFF suitable for WMS serving and visual comparison.

Encoding:
  [min_elevation, max_elevation] → [0, 254], 255 = nodata
  To decode: elevation_m = VALUE_MIN + (pixel / 254) * (VALUE_MAX - VALUE_MIN)

Delegates all processing to process_float32_cog (generic float32→uint8 COG).
"""

import logging

from processors.cog_float32 import process_float32_cog

logger = logging.getLogger(__name__)


def process_dtm(dtm_path: str, output_path: str, tile_size: int = 2048) -> str:
    """
    Convert a raw DTM GeoTIFF to a uint8 COG with global elevation normalization.

    Args:
        dtm_path:    Path to the source DTM GeoTIFF (float32, metres)
        output_path: Path for the uint8 COG output
        tile_size:   Processing tile size in pixels (default 2048)

    Returns:
        output_path
    """
    logger.info(f"Processing DTM: {dtm_path}")

    return process_float32_cog(
        input_path=dtm_path,
        output_path=output_path,
        tile_size=tile_size,
        extra_tags={"LAYER_TYPE": "DTM", "DATA_TYPE": "Elevation", "UNIT": "meters"},
    )
