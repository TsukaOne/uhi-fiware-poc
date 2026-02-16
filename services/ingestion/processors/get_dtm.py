from concurrent.futures import ThreadPoolExecutor
import time
import requests
import os
import math
import rasterio
from rasterio.merge import merge
from typing import Optional, Tuple
import logging

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
    cleanup_tiles: bool = True
) -> str:
    """
    Download a raster from a WCS service using tiled parallel downloads.
    
    Args:
        wcs_url: Base URL of the WCS service
        coverage: Name of the coverage to download
        bbox: Bounding box as (minx, miny, maxx, maxy)
        output_path: Path where the final merged raster will be saved
        crs: Coordinate reference system (default: EPSG:31370)
        resolution: Resolution in meters (default: 1.0)
        tile_size: Size of tiles in pixels (default: 10000)
        max_workers: Number of parallel download threads (default: 12)
        tile_dir: Directory to store temporary tiles (default: temp_tiles)
        cleanup_tiles: Whether to delete tiles after merging (default: True)
    
    Returns:
        Path to the downloaded raster file
    
    Example:
        >>> download_wcs_raster(
        ...     wcs_url="https://geoservices-urbis.irisnet.be/geoserver/urbisgrid/wcs",
        ...     coverage="urbisgrid:Altitude2019",
        ...     bbox=[140000, 160000, 159000, 179000],
        ...     output_path="dtm_output.tif"
        ... )
    """
    
    # Setup tile directory
    if tile_dir is None:
        tile_dir = f"temp_tiles_{int(time.time())}"
    os.makedirs(tile_dir, exist_ok=True)
    
    # Calculate total dimensions
    width_total = int((bbox[2] - bbox[0]) / resolution)
    height_total = int((bbox[3] - bbox[1]) / resolution)
    
    # Calculate tile grid
    tiles_x = math.ceil(width_total / tile_size)
    tiles_y = math.ceil(height_total / tile_size)
    dx = (bbox[2] - bbox[0]) / tiles_x
    dy = (bbox[3] - bbox[1]) / tiles_y
    
    logger.info(f"📊 WCS Download Configuration:")
    logger.info(f"   - Total resolution: {width_total}x{height_total} pixels")
    logger.info(f"   - Tile grid: {tiles_x}x{tiles_y} = {tiles_x * tiles_y} tiles")
    logger.info(f"   - Tile size: {tile_size}x{tile_size} pixels")
    logger.info(f"   - Parallel workers: {max_workers}")
    
    # Create download tasks
    tasks = []
    for ix in range(tiles_x):
        for iy in range(tiles_y):
            minx = bbox[0] + ix * dx
            maxx = bbox[0] + (ix + 1) * dx
            miny = bbox[1] + iy * dy
            maxy = bbox[1] + (iy + 1) * dy
            
            width = tile_size if ix < tiles_x - 1 else width_total - tile_size * ix
            height = tile_size if iy < tiles_y - 1 else height_total - tile_size * iy
            
            tile_name = f"tile_{ix}_{iy}.tif"
            tile_path = os.path.join(tile_dir, tile_name)
            
            tasks.append((minx, miny, maxx, maxy, width, height, tile_path, 
                         wcs_url, coverage, crs))
    
    logger.info(f"🚀 Starting downloads...")
    start_time = time.time()
    
    tile_paths = []
    failed_tiles = []
    
    # Download tiles in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {
            executor.submit(_download_tile, *task): task 
            for task in tasks
        }
        
        # Process completed downloads
        for future in future_to_task:
            try:
                tile_path, success = future.result()
                if success:
                    tile_paths.append(tile_path)
                else:
                    failed_tiles.append(tile_path)
            except Exception as e:
                logger.error(f"Task failed: {e}")
    
    download_time = time.time() - start_time
    logger.info(f"✅ Downloads completed in {download_time:.1f}s")
    logger.info(f"   - Successful: {len(tile_paths)}/{len(tasks)}")
    logger.info(f"   - Failed: {len(failed_tiles)}")
    
    if failed_tiles:
        logger.warning(f"⚠️  Failed tiles: {failed_tiles}")
        if len(failed_tiles) > len(tasks) * 0.1:  # More than 10% failed
            raise Exception(f"Too many tiles failed: {len(failed_tiles)}/{len(tasks)}")
    
    # Merge tiles
    logger.info(f"🔗 Merging tiles...")
    merge_start = time.time()
    
    src_files = [rasterio.open(p) for p in tile_paths if os.path.exists(p)]
    
    if not src_files:
        raise Exception("No valid tiles to merge")
    
    mosaic, out_trans = merge(src_files)
    
    out_meta = src_files[0].meta.copy()
    out_meta.update({
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": out_trans,
        "compress": "lzw"
    })
    
    with rasterio.open(output_path, "w", **out_meta) as dest:
        dest.write(mosaic)
    
    # Close source files
    for src in src_files:
        src.close()
    
    merge_time = time.time() - merge_start
    total_time = time.time() - start_time
    
    logger.info(f"✅ Raster saved: {output_path}")
    logger.info(f"⏱️  Execution time:")
    logger.info(f"   - Download: {download_time:.1f}s")
    logger.info(f"   - Merge: {merge_time:.1f}s")
    logger.info(f"   - Total: {total_time:.1f}s")
    logger.info(f"   - Speed: {len(tile_paths)/download_time:.1f} tiles/s")
    
    # Cleanup tiles if requested
    if cleanup_tiles:
        logger.info(f"🧹 Cleaning up temporary tiles...")
        for tile_path in tile_paths:
            try:
                os.remove(tile_path)
            except Exception as e:
                logger.warning(f"Failed to remove {tile_path}: {e}")
        
        try:
            os.rmdir(tile_dir)
        except Exception as e:
            logger.warning(f"Failed to remove tile directory: {e}")
    
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
    max_retries: int = 3
) -> Tuple[str, bool]:
    """
    Download a single tile from WCS service.
    
    Returns:
        Tuple of (tile_path, success)
    """
    # Skip if already exists
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
                logger.error(f"Failed after {max_retries} attempts: {out_path} - {e}")
                return out_path, False
            time.sleep(2 ** attempt)  # Exponential backoff
    
    return out_path, False


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Download DTM for Brussels
    download_wcs_raster(
        wcs_url="https://geoservices-urbis.irisnet.be/geoserver/urbisgrid/wcs",
        coverage="urbisgrid:Altitude2019",
        bbox=[140000, 160000, 159000, 179000],  # Brussels extent in EPSG:31370
        output_path="DTM_RBC_full.tif",
        resolution=1.0,
        tile_size=10000,
        max_workers=12
    )