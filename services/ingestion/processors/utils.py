"""
Shared raster processing utilities.

Provides common building blocks used by multiple processors:
- Tiled window iteration  (memory-safe processing of large rasters)
- Nodata detection        (for UrbIS orthophotos with 254/255 borders)
- Normalized difference   (base formula for NDVI, NDWI, NDBI, …)
"""

from typing import Generator, Tuple

import numpy as np
import rasterio
from rasterio.windows import Window


def iter_windows(height: int, width: int, tile_size: int) -> Generator[Window, None, None]:
    """
    Yield rasterio Windows for tiled processing of a raster.

    Divides the full raster into non-overlapping tiles. Edge tiles are
    automatically clipped to the raster boundary.

    Args:
        height:    Raster height in pixels
        width:     Raster width in pixels
        tile_size: Target tile size in pixels

    Yields:
        rasterio.windows.Window covering each tile, left-to-right, top-to-bottom
    """
    for row_off in range(0, height, tile_size):
        for col_off in range(0, width, tile_size):
            win_h = min(tile_size, height - row_off)
            win_w = min(tile_size, width - col_off)
            yield Window(col_off, row_off, win_w, win_h)


def detect_nodata_mask(
    src: rasterio.DatasetReader,
    window: Window,
    nodata_values: Tuple[int, ...] = (254, 255),
) -> np.ndarray:
    """
    Return a 2-D boolean mask where ALL bands carry a nodata value.

    A pixel is nodata only when every band matches one of nodata_values.
    This matches the convention in UrbIS orthophotos where values 254/255
    mark image borders rather than valid data.

    Args:
        src:           Open rasterio dataset (multi-band)
        window:        Tile window to read
        nodata_values: Pixel values treated as nodata (default: 254, 255)

    Returns:
        Boolean array of shape (height, width). True → nodata pixel.
    """
    bands = src.read(window=window)  # (n_bands, height, width)

    # A pixel is nodata only if ALL bands are nodata
    nodata_mask = np.ones(bands.shape[1:], dtype=bool)
    for band in bands:
        nodata_mask &= np.isin(band, nodata_values)

    return nodata_mask


def normalized_difference(band_a: np.ndarray, band_b: np.ndarray) -> np.ndarray:
    """
    Compute a normalized difference index: (A - B) / (A + B).

    Safe against divide-by-zero: returns 0 where (A + B) == 0.
    Result is clipped to [-1, 1] and returned as float32.

    Args:
        band_a: First band array  (appears positive in the numerator)
        band_b: Second band array (appears negative in the numerator)

    Returns:
        float32 array in [-1, 1]

    Examples:
        NDVI = normalized_difference(nir, red)
        NDWI = normalized_difference(green, nir)
    """
    a = band_a.astype(np.float32)
    b = band_b.astype(np.float32)
    denominator = a + b
    index = np.where(denominator != 0, (a - b) / denominator, 0.0)
    return np.clip(index, -1.0, 1.0).astype(np.float32)
