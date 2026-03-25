"""
LST (Land Surface Temperature) Processor

Converts a raw LST GeoTIFF (float32, temperature in °C) to a uint8
Cloud-Optimized GeoTIFF suitable for WMS serving and visual comparison.

Encoding:
  [min_temp, max_temp] → [0, 254], 255 = nodata
  To decode: temperature_C = VALUE_MIN + (pixel / 254) * (VALUE_MAX - VALUE_MIN)

Delegates all processing to process_float32_cog (generic float32→uint8 COG).
"""

import logging

from processors.cog_float32 import process_float32_cog

logger = logging.getLogger(__name__)


def process_lst(lst_path: str, output_path: str, tile_size: int = 2048) -> str:
    """
    Convert a raw LST GeoTIFF to a uint8 COG with global temperature normalization.

    Args:
        lst_path:    Path to the source LST GeoTIFF (float32, °C)
        output_path: Path for the uint8 COG output
        tile_size:   Processing tile size in pixels (default 2048)

    Returns:
        output_path
    """
    logger.info(f"Processing LST: {lst_path}")

    return process_float32_cog(
        input_path=lst_path,
        output_path=output_path,
        tile_size=tile_size,
        extra_tags={"LAYER_TYPE": "LST", "DATA_TYPE": "Temperature", "UNIT": "celsius"},
    )
