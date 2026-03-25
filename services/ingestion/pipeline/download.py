"""
Download helpers for the ingestion pipeline.

Each function downloads a remote file and extracts the relevant asset.
All functions skip the download if the target file already exists on disk.
"""

import asyncio
import logging
import shutil
import zipfile
from pathlib import Path
from typing import Optional

import httpx

from config import DATA_RAW_PATH
from processors.get_dtm import download_wcs_raster

logger = logging.getLogger(__name__)

# WCS parameters for the Brussels DTM (UrbIS grid)
_DTM_COVERAGE = "urbisgrid:Altitude2019"
_DTM_BBOX = [140000, 160000, 159000, 179000]  # Brussels extent in EPSG:31370
_DTM_RESOLUTION = 1                            # 1 m/px
_DTM_TILE_SIZE = 10000                         # 4 tiles cover the full extent
_DTM_MAX_WORKERS = 12


async def download_tiff_from_zip(url: str, name: str) -> Optional[Path]:
    """
    Download a ZIP archive and extract the first GeoTIFF found inside.

    Skips the download if a TIFF already exists in the extraction directory.

    Args:
        url:  Download URL for the ZIP file
        name: Short identifier used for the local zip path and extraction directory
              (e.g. "rgb", "nir")

    Returns:
        Path to the extracted GeoTIFF, or None on failure
    """
    extract_dir = DATA_RAW_PATH / name

    if extract_dir.exists():
        existing = list(extract_dir.rglob("*.tif")) + list(extract_dir.rglob("*.tiff"))
        if existing:
            logger.info(f"Skipping '{name}': found existing TIFF at {existing[0]}")
            return existing[0]

    zip_path = DATA_RAW_PATH / f"{name}.zip"
    try:
        await _stream_download(url, zip_path)
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        tiff_files = list(extract_dir.rglob("*.tif")) + list(extract_dir.rglob("*.tiff"))
        if tiff_files:
            return tiff_files[0]

        logger.error(f"No TIFF found in extracted archive for '{name}'")
        return None

    except Exception as e:
        logger.error(f"Failed to download/extract '{name}' from {url}: {e}")
        return None


async def download_gpkg_from_zip(url: str, name: str, gpkg_name_contains: str) -> Optional[Path]:
    """
    Download a ZIP archive and extract a specific GeoPackage file.

    Only the first .gpkg whose filename contains gpkg_name_contains is extracted.
    Skips the download if a matching file already exists.

    Args:
        url:                Download URL for the ZIP archive
        name:               Short identifier for the local zip path and extraction directory
        gpkg_name_contains: Substring used to identify the target .gpkg inside the archive

    Returns:
        Path to the extracted GeoPackage, or None on failure
    """
    extract_dir = DATA_RAW_PATH / name

    if extract_dir.exists():
        existing = list(extract_dir.rglob(f"*{gpkg_name_contains}*.gpkg"))
        if existing:
            logger.info(f"Skipping '{name}': found existing GPKG at {existing[0]}")
            return existing[0]

    zip_path = DATA_RAW_PATH / f"{name}.zip"
    try:
        await _stream_download(url, zip_path)
        extract_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                if member.lower().endswith(".gpkg") and gpkg_name_contains.lower() in member.lower():
                    target = extract_dir / Path(member).name
                    with zf.open(member) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    logger.info(f"Extracted GPKG: {target}")
                    return target

        logger.error(f"No GPKG matching '{gpkg_name_contains}' found in {zip_path}")
        return None

    except Exception as e:
        logger.error(f"Failed to download/extract '{name}' from {url}: {e}")
        return None


async def download_dtm(wcs_url: str) -> Path:
    """
    Download the Brussels DTM from the WCS service if not already present.

    Uses tiled parallel downloads; see processors.get_dtm for details.

    Args:
        wcs_url: Base URL of the WCS service

    Returns:
        Path to the DTM GeoTIFF
    """
    output_path = DATA_RAW_PATH / "dtm_brussels.tif"

    if output_path.exists():
        logger.info(f"DTM already exists at {output_path}, skipping download")
        return output_path

    logger.info("Downloading DTM from WCS service...")
    await asyncio.to_thread(
        download_wcs_raster,
        wcs_url=wcs_url,
        coverage=_DTM_COVERAGE,
        bbox=_DTM_BBOX,
        output_path=str(output_path),
        resolution=_DTM_RESOLUTION,
        tile_size=_DTM_TILE_SIZE,
        max_workers=_DTM_MAX_WORKERS,
        cleanup_tiles=True,
    )
    return output_path


async def run_if_missing(output_path: Path, func, *args) -> None:
    """
    Run a synchronous processing function only if its output file is missing.

    Runs in a thread pool via asyncio.to_thread so the event loop stays free.

    Args:
        output_path: Expected output — the function is skipped if it already exists
        func:        Synchronous function to call
        *args:       Arguments forwarded to func
    """
    if output_path.exists():
        logger.info(f"Skipping (already exists): {output_path.name}")
        return
    await asyncio.to_thread(func, *args)
    logger.info(f"Created: {output_path.name}")


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _stream_download(url: str, dest: Path) -> None:
    """Stream-download url to dest using an async HTTP client."""
    logger.info(f"Downloading: {url}")
    async with httpx.AsyncClient(timeout=600.0) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            with open(dest, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    f.write(chunk)
    logger.info(f"Downloaded: {dest}")
