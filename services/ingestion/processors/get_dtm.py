"""
WCS DTM Downloader

Downloads a Digital Terrain Model raster from an OGC Web Coverage Service (WCS)
using tiled parallel downloads to handle large coverages efficiently.

Strategy:
  1. Divide the target bounding box into a grid of tiles (default 10 000 px each)
  2. Download all tiles in parallel using a thread pool
  3. Merge the tiles into a single output GeoTIFF

Tiles that fail are retried with exponential backoff (up to 3 attempts).
The pipeline aborts if more than 10% of tiles fail.
"""

import logging
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Tuple

import rasterio
import requests
from rasterio.merge import merge

logger = logging.getLogger(__name__)


def download_wcs_raster(
    wcs_url: str,
    coverage: str,
    bbox: Tuple[float, float, float, float],
    output_path: str,
    crs: str = "EPSG:31370",
    resolution: float = 0.4,
    tile_size: int = 10000,
    max_workers: int = 12,
    tile_dir: Optional[str] = None,
    cleanup_tiles: bool = True,
) -> str:
    """
    Download a raster from a WCS service using tiled parallel downloads.

    Args:
        wcs_url:       Base URL of the WCS service
        coverage:      Coverage identifier (e.g. "urbisgrid:Altitude2019")
        bbox:          Bounding box as (minx, miny, maxx, maxy) in the target CRS
        output_path:   Path where the final merged raster will be saved
        crs:           Coordinate reference system (default: EPSG:31370)
        resolution:    Pixel resolution in metres (default: 0.4 m)
        tile_size:     Tile size in pixels (default: 10 000)
        max_workers:   Number of parallel download threads (default: 12)
        tile_dir:      Temporary directory for tiles (auto-generated if None)
        cleanup_tiles: Delete tile files after merging (default: True)

    Returns:
        Path to the downloaded and merged raster file

    Example:
        download_wcs_raster(
            wcs_url="https://geoservices-urbis.irisnet.be/geoserver/urbisgrid/wcs",
            coverage="urbisgrid:Altitude2019",
            bbox=[140000, 160000, 159000, 179000],
            output_path="dtm_brussels.tif",
        )
    """
    if tile_dir is None:
        tile_dir = f"temp_tiles_{int(time.time())}"
    os.makedirs(tile_dir, exist_ok=True)

    # Compute total raster dimensions and tile grid
    width_total = int((bbox[2] - bbox[0]) / resolution)
    height_total = int((bbox[3] - bbox[1]) / resolution)
    tiles_x = math.ceil(width_total / tile_size)
    tiles_y = math.ceil(height_total / tile_size)
    dx = (bbox[2] - bbox[0]) / tiles_x
    dy = (bbox[3] - bbox[1]) / tiles_y

    logger.info(f"WCS download: {width_total}x{height_total} px, {tiles_x}x{tiles_y} tile grid")
    logger.info(f"Coverage: {coverage}, workers: {max_workers}")

    # Build list of download tasks
    tasks = []
    for ix in range(tiles_x):
        for iy in range(tiles_y):
            minx = bbox[0] + ix * dx
            maxx = bbox[0] + (ix + 1) * dx
            miny = bbox[1] + iy * dy
            maxy = bbox[1] + (iy + 1) * dy

            tile_width = tile_size if ix < tiles_x - 1 else width_total - tile_size * ix
            tile_height = tile_size if iy < tiles_y - 1 else height_total - tile_size * iy

            tile_path = os.path.join(tile_dir, f"tile_{ix}_{iy}.tif")
            tasks.append((minx, miny, maxx, maxy, tile_width, tile_height, tile_path, wcs_url, coverage, crs))

    logger.info(f"Starting download of {len(tasks)} tiles...")
    start_time = time.time()

    tile_paths = []
    failed_tiles = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {executor.submit(_download_tile, *task): task[6] for task in tasks}
        for future in as_completed(future_to_path):
            try:
                tile_path, success = future.result()
                if success:
                    tile_paths.append(tile_path)
                else:
                    failed_tiles.append(tile_path)
            except Exception as e:
                logger.error(f"Download task raised an exception: {e}")

    download_time = time.time() - start_time
    logger.info(f"Downloads done in {download_time:.1f}s — {len(tile_paths)} ok, {len(failed_tiles)} failed")

    if failed_tiles:
        logger.warning(f"Failed tiles: {failed_tiles}")
        if len(failed_tiles) > len(tasks) * 0.1:
            raise RuntimeError(f"Too many tiles failed: {len(failed_tiles)}/{len(tasks)}")

    # Merge tiles into a single output raster
    logger.info("Merging tiles into final raster...")
    merge_start = time.time()

    src_files = [rasterio.open(p) for p in tile_paths if os.path.exists(p)]
    if not src_files:
        raise RuntimeError("No valid tiles to merge")

    mosaic, out_transform = merge(src_files)
    out_meta = src_files[0].meta.copy()
    out_meta.update(height=mosaic.shape[1], width=mosaic.shape[2], transform=out_transform, compress="lzw")

    with rasterio.open(output_path, "w", **out_meta) as dest:
        dest.write(mosaic)

    for src in src_files:
        src.close()

    merge_time = time.time() - merge_start
    total_time = time.time() - start_time
    logger.info(
        f"Raster saved: {output_path} "
        f"(download: {download_time:.1f}s, merge: {merge_time:.1f}s, total: {total_time:.1f}s)"
    )

    if cleanup_tiles:
        logger.info("Cleaning up temporary tile files...")
        for tile_path in tile_paths:
            try:
                os.remove(tile_path)
            except Exception as e:
                logger.warning(f"Could not remove tile {tile_path}: {e}")
        try:
            os.rmdir(tile_dir)
        except Exception as e:
            logger.warning(f"Could not remove tile directory {tile_dir}: {e}")

    return output_path


def _download_tile(
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
    width: int,
    height: int,
    out_path: str,
    wcs_url: str,
    coverage: str,
    crs: str,
    max_retries: int = 3,
) -> Tuple[str, bool]:
    """
    Download a single WCS tile with exponential-backoff retry.

    Returns:
        (tile_path, success) tuple
    """
    if os.path.exists(out_path):
        return out_path, True

    params = {
        "SERVICE": "WCS",
        "VERSION": "1.0.0",
        "REQUEST": "GetCoverage",
        "COVERAGE": coverage,
        "CRS": crs,
        "BBOX": f"{minx},{miny},{maxx},{maxy}",
        "WIDTH": str(width),
        "HEIGHT": str(height),
        "FORMAT": "GeoTIFF",
    }

    for attempt in range(max_retries):
        try:
            response = requests.get(wcs_url, params=params, stream=True, timeout=120)
            response.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
            return out_path, True
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Tile failed after {max_retries} attempts: {out_path} — {e}")
                return out_path, False
            time.sleep(2 ** attempt)  # 1s, 2s, 4s backoff

    return out_path, False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    download_wcs_raster(
        wcs_url="https://geoservices-urbis.irisnet.be/geoserver/urbisgrid/wcs",
        coverage="urbisgrid:Altitude2019",
        bbox=[140000, 160000, 159000, 179000],
        output_path="dtm_brussels.tif",
        resolution=1.0,
        tile_size=10000,
        max_workers=12,
    )
