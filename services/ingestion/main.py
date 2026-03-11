"""
UHI Data Ingestion Service

FastAPI service for downloading orthophotos from UrbIS, 
processing NDVI/NDWI indices, and registering layers in Orion-LD.
"""

import os
import asyncio
import logging
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

from processors.ndvi import calculate_ndvi
from processors.ndwi import calculate_ndwi
from processors.dtm import process_dtm
from processors.building_height import process_building_heights
from processors.cog import build_overviews
from fiware.client import OrionClient, GeoSpatialLayer
from processors.get_dtm import download_wcs_raster
from processors.lst import process_lst
from processors.cog_float32 import process_float32_cog
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
"""
# For testing locally
from dotenv import load_dotenv
BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)
#DURING TESTING, REVERT TO THIS:
DATA_RAW_PATH = Path(BASE_DIR / os.getenv("DATA_RAW_PATH", "/data/raw"))
DATA_PROCESSED_PATH = Path(BASE_DIR / os.getenv("DATA_PROCESSED_PATH", "/data/processed"))"""


# Environment variables
ORION_URL = os.getenv("ORION_URL", "http://orion:1026")
DATA_RAW_PATH = Path(os.getenv("DATA_RAW_PATH", "/data/raw"))
DATA_PROCESSED_PATH = Path(os.getenv("DATA_PROCESSED_PATH", "/data/processed"))
RGB_URL = os.getenv("RGB_URL", "")
NIR_URL = os.getenv("NIR_URL", "")
DTM_URL = os.getenv("DTM_URL", "")
BUILDINGS_AND_ENGINEERING_WORKS_URL = os.getenv("BUILDINGS_AND_ENGINEERING_WORKS_URL", "")

# Ensure directories exist
DATA_RAW_PATH.mkdir(parents=True, exist_ok=True)
DATA_PROCESSED_PATH.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Starting UHI Ingestion Service")
    logger.info(f"Orion URL: {ORION_URL}")
    logger.info(f"Raw data path: {DATA_RAW_PATH}")
    logger.info(f"Processed data path: {DATA_PROCESSED_PATH}")
    yield
    logger.info("Shutting down UHI Ingestion Service")


app = FastAPI(
    title="UHI Data Ingestion Service",
    description="Download and process orthophotos, register layers in FIWARE Orion-LD",
    version="1.0.0",
    lifespan=lifespan,
)

# Initialize Orion client
orion_client = OrionClient(ORION_URL)


class IngestRequest(BaseModel):
    """Request model for orthophoto ingestion."""
    rgb_url: Optional[str] = None
    nir_url: Optional[str] = None
    dtm_url: Optional[str] = None
    buildings_and_engineering_works_url: Optional[str] = None


class IngestResponse(BaseModel):
    """Response model for ingestion status."""
    status: str
    message: str
    layers: list[str] = []


class LayerInfo(BaseModel):
    """Information about a registered layer."""
    id: str
    name: str
    layer_type: str
    file_path: str
    geoserver_layer: str


# Track ingestion status
ingestion_status = {
    "running": False,
    "progress": "",
    "layers_created": []
}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "ingestion"}


@app.get("/status")
async def get_status():
    """Get current ingestion status."""
    return ingestion_status


@app.get("/layers", response_model=list[LayerInfo])
async def list_layers():
    """List all registered GeoSpatialLayer entities from Orion."""
    try:
        layers = await orion_client.get_all_layers()
        return [
            LayerInfo(
                id=layer.get("id", ""),
                name=layer.get("name", {}).get("value", ""),
                layer_type=layer.get("layerType", {}).get("value", ""),
                file_path=layer.get("filePath", {}).get("value", ""),
                geoserver_layer=layer.get("geoserverLayer", {}).get("value", "")
            )
            for layer in layers
        ]
    except Exception as e:
        logger.error(f"Failed to list layers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/orthophotos", response_model=IngestResponse)
async def ingest_orthophotos(
    background_tasks: BackgroundTasks,
    request: Optional[IngestRequest] = None
):
    """
    Download and process orthophotos from UrbIS.
    
    This endpoint triggers the full ingestion pipeline:
    1. Download RGB, NIR orthophotos + DTM 
    2. Extract GeoTIFF files
    3. Calculate NDVI and NDWI indices
    4. Register all layers in Orion-LD
    
    Can be called without a body to use default URLs from environment.
    """
    if ingestion_status["running"]:
        raise HTTPException(
            status_code=409,
            detail="Ingestion already in progress"
        )
    
    rgb_url = (request.rgb_url if request else None) or RGB_URL
    nir_url = (request.nir_url if request else None) or NIR_URL
    dtm_url = (request.dtm_url if request else None) or DTM_URL
    building_and_engineering_works_url = (request.buildings_and_engineering_works_url if request else None) or BUILDINGS_AND_ENGINEERING_WORKS_URL
    
    logger.info(f"Starting ingestion with URLs: RGB={rgb_url}, NIR={nir_url}, DTM={dtm_url}, Buildings and Engineering Works={building_and_engineering_works_url}")
    
    if not dtm_url:
        raise HTTPException(
            status_code=400,
            detail="DTM URL is required"
        )
    
    if not building_and_engineering_works_url:
        raise HTTPException(
            status_code=400,
            detail="Buildings and Engineering Works URL is required"
        )
    
    if not rgb_url or not nir_url:
        raise HTTPException(
            status_code=400,
            detail="RGB and NIR URLs are required"
        )
    
    # Start background ingestion
    background_tasks.add_task(
        run_ingestion_pipeline,
        rgb_url,
        nir_url,
        dtm_url,
        building_and_engineering_works_url
    )
    
    return IngestResponse(
        status="started",
        message="Ingestion pipeline started in background",
        layers=[]
    )

async def download_dtm_wcs(dtm_url: str, output_dir: Path) -> Path:
    """
    Download DTM from WCS service.
    
    Args:
        dtm_url: URL of the WCS service (or can be used as a marker to use WCS)
        output_dir: Directory where the DTM will be saved
        
    Returns:
        Path to the downloaded DTM file
    """
    output_path = output_dir / "dtm_brussels.tif"
    
    # Check if already downloaded
    if output_path.exists():
        logger.info(f"DTM already exists at {output_path}, skipping download")
        return output_path
    
    logger.info("Downloading DTM from WCS service...")
    
    # Run the WCS download in a thread to not block the async loop
    await asyncio.to_thread(
        download_wcs_raster,
        wcs_url=dtm_url,
        coverage="urbisgrid:Altitude2019",# WCS Layer
        bbox=[140000, 160000, 159000, 179000],  # BBOX for Brussels extent in EPSG:31370 (it includes no data value too)
        output_path=str(output_path),
        resolution=1,# 1m
        tile_size=10000,# 4 chunk for 1 big raster
        max_workers=12,# Number max of thread
        cleanup_tiles=True  # Clean up temporary tiles after merge
    )
    
    return output_path

async def run_if_missing(output_path: Path, func, *args):
    """
    Check if the file exist in the path and run the script for preprocessing

    Args:
        output_path: Path of the file
        func: function to run if path is missing
        *args: additionial args 
    """
    if output_path.exists():
        logger.info(f"Skipping (already exists): {output_path.name}")
        return
    await asyncio.to_thread(func, *args)
    logger.info(f"Created: {output_path.name}")


async def run_ingestion_pipeline(rgb_url: str, nir_url: str, dtm_url: str, building_and_engineering_works_url: str):
    """Run the full ingestion pipeline."""
    global ingestion_status
    
    ingestion_status = {
        "running": True,
        "progress": "Starting ingestion...",
        "layers_created": []
    }
    
    try:
        # Step 1: Download orthophotos and DTM (if not already downloaded)
        ingestion_status["progress"] = "Downloading RGB orthophoto..."
        logger.info(f"Downloading RGB from: {rgb_url}")
        rgb_path = await download_and_extract(rgb_url, "rgb")
        
        ingestion_status["progress"] = "Downloading NIR orthophoto..."
        logger.info(f"Downloading NIR from: {nir_url}")
        nir_path = await download_and_extract(nir_url, "nir")

        ingestion_status["progress"] = "Downloading Buildings and engineering data from GeoPackage..."
        logger.info(f"Downloading Buildings and engineering data from GeoPackage")
        building_and_engineering_works_path = await download_and_extract_zip_gpkg(building_and_engineering_works_url, "buildings_and_engineering_works","UrbISBuildings3D_04000")

        ingestion_status["progress"] = "Downloading DTM from WCS (tiled download)..."
        logger.info(f"Downloading DTM via WCS")
        dtm_path = await download_dtm_wcs(dtm_url, DATA_RAW_PATH)
        
        # LST: use pre-existing raw file if available (no WCS source configured yet)
        lst_path = DATA_PROCESSED_PATH / "lst.tif"
        logger.info(f"Checking for LST raw file at: {lst_path}")
        lst_available = lst_path.exists()
        if not lst_available:
            logger.warning(f"LST raw file not found at {lst_path}, LST layer will be skipped")

        if not rgb_path or not nir_path:
            raise Exception("Failed to download orthophotos")

        if not dtm_path:
            raise Exception("Failed to download DTM")

        if not building_and_engineering_works_path:
            raise Exception("Failed to download buildings and engineering data")
        
        # Use raw files directly (no copying to save disk space and memory)
        rgb_processed = rgb_path
        nir_processed = nir_path
        dtm_processed = dtm_path
        building_and_engineering_works_processed = building_and_engineering_works_path

        logger.info(f"Using RGB directly from: {rgb_processed}")
        logger.info(f"Using NIR directly from: {nir_processed}")
        logger.info(f"Using DTM directly from: {dtm_processed}")
        logger.info(f"Using Buildings and Engineering Works directly from: {building_and_engineering_works_processed}")
        
        # Step 1b: Build overviews for RGB and NIR (critical for WMS performance)
        # Without overviews, GeoServer reads the full 6GB file at every zoom level
        ingestion_status["progress"] = "Building RGB overviews for fast WMS serving..."
        await asyncio.to_thread(build_overviews, str(rgb_processed))
        
        ingestion_status["progress"] = "Building NIR overviews for fast WMS serving..."
        await asyncio.to_thread(build_overviews, str(nir_processed))
        
        ingestion_status["progress"] = "Building DTM overviews for fast WMS serving..."
        await asyncio.to_thread(build_overviews, str(dtm_processed))

        # Step 2: Calculate NDVI (using windowed processing for large files)
        ingestion_status["progress"] = "Calculating NDVI (windowed processing)..."
        ndvi_path = DATA_PROCESSED_PATH / "ndvi_brussels_2024.tif"
        await run_if_missing(
            ndvi_path,
            calculate_ndvi,
            str(rgb_processed),
            str(nir_processed),
            str(ndvi_path)
        )

        logger.info(f"NDVI calculated: {ndvi_path}")
        
        # Step 3: Calculate NDWI (using windowed processing for large files)
        ingestion_status["progress"] = "Calculating NDWI (windowed processing)..."
        ndwi_path = DATA_PROCESSED_PATH / "ndwi_brussels_2024.tif"
        await run_if_missing(
            ndwi_path,
            calculate_ndwi,
            str(rgb_processed),
            str(nir_processed),
            str(ndwi_path)
        )
        logger.info(f"NDWI calculated: {ndwi_path}")

        # Step 4: Process DTM (convert to COG with overviews)
        ingestion_status["progress"]= "Processing DTM (convert to COG with overviews)..."
        dtm_cog_path = DATA_PROCESSED_PATH / "dtm_brussels_2021.tif"
        await run_if_missing(
            dtm_cog_path,
            process_dtm,
            str(dtm_processed),
            str(dtm_cog_path)
        )
        logger.info(f"DTM processed: {dtm_cog_path}")

        # Step 5: Calculate Relative building height using DTM and buildings data gpkg
        ingestion_status["progress"] = "Calculating Relative building height using DTM and buildings data gpkg..."
        building_height_path = DATA_PROCESSED_PATH / "building_height_brussels.tif"
        await run_if_missing(
            building_height_path,
            process_building_heights,
            str(building_and_engineering_works_processed),
            str(dtm_path),
            str(building_height_path),
            "BuildingFaces"
        )

        # Step 6: Calculate LST (Land Surface Temperature) — only if raw file exists
        lst_cog_path = DATA_PROCESSED_PATH / "lst_cog_2024.tif"
        logger.info(f"Checking for LST COG at: {lst_cog_path}")
        if lst_available:
            ingestion_status["progress"] = "Calculating LST (Land Surface Temperature)..."
            logger.info("Calculating LST (Land Surface Temperature)...")
            await run_if_missing(
                lst_cog_path,
                process_lst,
                str(lst_path),
                str(lst_cog_path)
            )
        # Step 7: Convert raw float32 layers to COG (DSM, NDBI, Imperviousness, Albedo)
        raw_to_cog = [
            ("dsm.tif",             "dsm_brussels_2024.tif",             "DSM"),
            ("ndbi.tif",            "ndbi_brussels_2024.tif",            "NDBI"),
            ("imperviousness.tif",  "imperviousness_brussels_2024.tif",  "Imperviousness"),
            ("albedo.tif",          "albedo_brussels_2024.tif",          "Albedo"),
        ]
        for raw_name, cog_name, label in raw_to_cog:
            raw_file = DATA_RAW_PATH / raw_name
            cog_file = DATA_PROCESSED_PATH / cog_name
            if raw_file.exists():
                ingestion_status["progress"] = f"Converting {label} to COG..."
                await run_if_missing(
                    cog_file,
                    process_float32_cog,
                    str(raw_file),
                    str(cog_file),
                )
            else:
                logger.warning(f"Raw {label} not found at {raw_file}, skipping COG conversion")

        # Step 8: Register layers in Orion
        ingestion_status["progress"] = "Registering layers in Orion..."
        
        layers_to_register = [
            GeoSpatialLayer(
                layer_type="RGB",
                name="RGB Brussels 2024",
                spectral_range="RGB",
                file_path=str(rgb_processed),
                resolution=40
            ),
            GeoSpatialLayer(
                layer_type="NIR",
                name="NIR Brussels 2024",
                spectral_range="NIR",
                file_path=str(nir_processed),
                resolution=40
            ),
            GeoSpatialLayer(
                layer_type="NDVI",
                name="NDVI Brussels 2024",
                spectral_range="computed",
                file_path=str(ndvi_path),
                resolution=40
            ),
            GeoSpatialLayer(
                layer_type="NDWI",
                name="NDWI Brussels 2024",
                spectral_range="computed",
                file_path=str(ndwi_path),
                resolution=40
            ),
            GeoSpatialLayer(
                layer_type="DTM",
                name="DTM Brussels 2021",
                spectral_range="elevation",
                file_path=str(dtm_cog_path),
                resolution=100
            ),
            GeoSpatialLayer(
                layer_type="BuildingHeight",
                name="Building Height Brussels 2024",
                spectral_range="elevation",
                file_path=str(building_height_path),
                resolution= 40
            ),
            *(
                [GeoSpatialLayer(
                    layer_type="LST",
                    name="LST Brussels 2024",
                    spectral_range="temperature",
                    file_path=str(lst_cog_path),
                    resolution=40
                )] if lst_available and lst_cog_path.exists() else []
            ),
        ]

        # ── Register COG float32 layers (DSM, NDBI, imperviousness, albedo)
        for raw_name, cog_name, label in raw_to_cog:
            cog_file = DATA_PROCESSED_PATH / cog_name
            if cog_file.exists():
                spectral = "elevation" if label == "DSM" else "computed"
                res = 100 if label == "DSM" else 40
                layers_to_register.append(GeoSpatialLayer(
                    layer_type=label,
                    name=f"{label} Brussels 2024",
                    spectral_range=spectral,
                    file_path=str(cog_file),
                    resolution=res,
                ))
            else:
                logger.warning(f"Skipping {label}: COG not found at {cog_file}")
        
        for layer in layers_to_register:
            try:
                await orion_client.create_or_update_layer(layer)
                ingestion_status["layers_created"].append(layer.layer_type)
                logger.info(f"Registered layer: {layer.layer_type}")
            except Exception as e:
                logger.error(f"Failed to register {layer.layer_type}: {e}")
        
        ingestion_status["progress"] = "Ingestion complete!"
        logger.info("Ingestion pipeline completed successfully")
        
    except Exception as e:
        logger.error(f"Ingestion pipeline failed: {e}")
        ingestion_status["progress"] = f"Error: {str(e)}"
    finally:
        ingestion_status["running"] = False


async def download_and_extract(url: str, name: str) -> Optional[Path]:
    """Download a ZIP file and extract the GeoTIFF. Skip if already exists."""
    import httpx
    import zipfile
    
    zip_path = DATA_RAW_PATH / f"{name}.zip"
    extract_dir = DATA_RAW_PATH / name
    
    try:
        # Check if already extracted and has TIFF files
        if extract_dir.exists():
            tiff_files = list(extract_dir.rglob("*.tif")) + list(extract_dir.rglob("*.tiff"))
            if tiff_files:
                logger.info(f"Skipping download for {name}: found existing TIFF at {tiff_files[0]}")
                return tiff_files[0]
        
        # Download the file
        async with httpx.AsyncClient(timeout=600.0) as client:
            logger.info(f"Starting download: {url}")
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with open(zip_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
        
        logger.info(f"Downloaded: {zip_path}")
        
        # Extract the ZIP
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        logger.info(f"Extracted to: {extract_dir}")
        
        # Find the TIFF file
        tiff_files = list(extract_dir.rglob("*.tif")) + list(extract_dir.rglob("*.tiff"))
        if tiff_files:
            return tiff_files[0]
        
        logger.error(f"No TIFF files found in {extract_dir}")
        return None
        
    except Exception as e:
        logger.error(f"Failed to download/extract {url}: {e}")
        return None
async def download_and_extract_zip_gpkg(url: str,name: str,gpkg_name_contains: str) -> Optional[Path]:
    """
    Download a ZIP file and extract a specific GPKG file matching gpkg_name_contains.
    """
    import httpx
    import zipfile
    import shutil

    zip_path = DATA_RAW_PATH / f"{name}.zip"
    extract_dir = DATA_RAW_PATH / name

    try:
        if extract_dir.exists():
            existing_gpkg = list(
                extract_dir.rglob(f"*{gpkg_name_contains}*.gpkg")
            )
            if existing_gpkg:
                logger.info(
                    f"Skipping download for {name}: found existing GPKG at {existing_gpkg[0]}"
                )
                return existing_gpkg[0]

        async with httpx.AsyncClient(timeout=600.0) as client:
            logger.info(f"Starting download: {url}")
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with open(zip_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)

        logger.info(f"Downloaded: {zip_path}")

        extract_dir.mkdir(parents=True, exist_ok=True)

        extracted_gpkg_path = None

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            for member in zip_ref.namelist():
                if member.lower().endswith(".gpkg") and gpkg_name_contains.lower() in member.lower():
                    
                    target_path = extract_dir / Path(member).name
                    
                    with zip_ref.open(member) as source, open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)

                    extracted_gpkg_path = target_path
                    logger.info(f"Extracted GPKG: {target_path}")
                    break

        if extracted_gpkg_path:
            return extracted_gpkg_path

        logger.error(f"No matching GPKG found in {zip_path}")
        return None

    except Exception as e:
        logger.error(f"Failed to download/extract {url}: {e}")
        return None


async def copy_geotiff(src: Path, dst: Path):
    """Copy a GeoTIFF file."""
    import shutil
    await asyncio.to_thread(shutil.copy2, src, dst)
    logger.info(f"Copied {src} to {dst}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

