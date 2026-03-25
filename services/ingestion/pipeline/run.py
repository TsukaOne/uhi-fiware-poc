"""
Ingestion pipeline orchestration.

The pipeline is split into four independent phases, each with a single
responsibility. run_ingestion_pipeline() calls them in order and keeps
the global status dict up to date between phases.

  Phase 1 — Download    : fetch all raw source files
  Phase 2 — Overviews   : build WMS pyramids on raw rasters
  Phase 3 — Compute     : derive NDVI, NDWI, DTM COG, building heights, …
  Phase 4 — Register    : upsert every layer in Orion-LD
"""

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from config import DATA_PROCESSED_PATH, DATA_RAW_PATH, ORION_URL
from fiware.client import GeoSpatialLayer, OrionClient
from pipeline.download import (
    download_dtm,
    download_gpkg_from_zip,
    download_tiff_from_zip,
    run_if_missing,
)
from processors.building_height import process_building_heights
from processors.cog import build_overviews
from processors.cog_float32 import process_float32_cog
from processors.dtm import process_dtm
from processors.lst import process_lst
from processors.ndvi import calculate_ndvi
from processors.ndwi import calculate_ndwi

logger = logging.getLogger(__name__)
orion_client = OrionClient(ORION_URL)

# ── Shared pipeline state (read by /status endpoint) ─────────────────────────

ingestion_status: dict = {
    "running": False,
    "progress": "",
    "layers_created": [],
}

# ── Data structures passed between phases ─────────────────────────────────────

@dataclass
class SourceData:
    """Raw files downloaded in Phase 1."""
    rgb: Path
    nir: Path
    dtm: Path
    buildings: Path
    lst_raw: Optional[Path]   # Pre-existing LST file; None if not available


@dataclass
class DerivedLayers:
    """Processed files produced in Phase 3."""
    ndvi: Path
    ndwi: Path
    dtm_cog: Path
    building_height: Path
    lst_cog: Optional[Path]
    optional_cogs: dict = field(default_factory=dict)  # label -> Path (DSM, NDBI, …)


# ── Phase 1: Download ─────────────────────────────────────────────────────────

async def _download_all_sources(
    rgb_url: str,
    nir_url: str,
    dtm_url: str,
    buildings_url: str,
) -> SourceData:
    """Download all raw source files, skipping those already on disk.
       RBG, NIR, DTM and building footprints are dowloaded from urls for proof of concept that we can download from the internet.
       Other files are pre-placed in the raw data folder, as they have no automated download source (LST, DSM, NDBI, Imperviousness, Albedo). 
    """
    ingestion_status["progress"] = "Downloading RGB orthophoto..."
    rgb = await download_tiff_from_zip(rgb_url, "rgb")

    ingestion_status["progress"] = "Downloading NIR orthophoto..."
    nir = await download_tiff_from_zip(nir_url, "nir")

    ingestion_status["progress"] = "Downloading 3D building footprints..."
    buildings = await download_gpkg_from_zip(
        buildings_url, "buildings_and_engineering_works", "UrbISBuildings3D_04000"
    )

    ingestion_status["progress"] = "Downloading DTM from WCS..."
    dtm = await download_dtm(dtm_url)

    if not rgb or not nir:
        raise RuntimeError("Failed to download RGB or NIR orthophoto")
    if not dtm:
        raise RuntimeError("Failed to download DTM")
    if not buildings:
        raise RuntimeError("Failed to download building footprints")

    # LST has no WCS source yet — must be pre-placed in DATA_PROCESSED_PATH
    lst_raw = DATA_PROCESSED_PATH / "lst.tif"
    if not lst_raw.exists():
        logger.warning(f"LST source not found at {lst_raw} — LST layer will be skipped")
        lst_raw = None

    return SourceData(rgb=rgb, nir=nir, dtm=dtm, buildings=buildings, lst_raw=lst_raw)


# ── Phase 2: WMS overviews ────────────────────────────────────────────────────

async def _build_source_overviews(sources: SourceData) -> None:
    """
    Build internal overview pyramids on the raw rasters.

    Without overviews GeoServer reads the full file for every zoom level --> making WMS requests 10-100x slower.
    """
    ingestion_status["progress"] = "Building WMS overviews on raw rasters..."
    for label, path in [("RGB", sources.rgb), ("NIR", sources.nir), ("DTM", sources.dtm)]:
        logger.info(f"Building overviews: {label}")
        await asyncio.to_thread(build_overviews, str(path))


# ── Phase 3: Compute derived layers ──────────────────────────────────────────

async def _compute_derived_layers(sources: SourceData) -> DerivedLayers:
    """Compute all derived raster layers from the raw source data."""
    # Spectral indices (NDVI, NDWI)
    ingestion_status["progress"] = "Calculating NDVI..."
    ndvi_path = DATA_PROCESSED_PATH / "ndvi_brussels_2024.tif"
    await run_if_missing(ndvi_path, calculate_ndvi, str(sources.rgb), str(sources.nir), str(ndvi_path))

    ingestion_status["progress"] = "Calculating NDWI..."
    ndwi_path = DATA_PROCESSED_PATH / "ndwi_brussels_2024.tif"
    await run_if_missing(ndwi_path, calculate_ndwi, str(sources.rgb), str(sources.nir), str(ndwi_path))

    # Elevation layers
    ingestion_status["progress"] = "Converting DTM to COG..."
    dtm_cog_path = DATA_PROCESSED_PATH / "dtm_brussels_2021.tif"
    await run_if_missing(dtm_cog_path, process_dtm, str(sources.dtm), str(dtm_cog_path))

    ingestion_status["progress"] = "Computing relative building heights..."
    building_height_path = DATA_PROCESSED_PATH / "building_height_brussels.tif"
    await run_if_missing(
        building_height_path,
        process_building_heights,
        str(sources.buildings),
        str(sources.dtm),
        str(building_height_path),
        "BuildingFaces",
    )

    # Optional: Land Surface Temperature
    lst_cog_path = None
    if sources.lst_raw:
        ingestion_status["progress"] = "Converting LST to COG..."
        lst_cog_path = DATA_PROCESSED_PATH / "lst_cog_2024.tif"
        await run_if_missing(lst_cog_path, process_lst, str(sources.lst_raw), str(lst_cog_path))

    # Optional float32 layers: place raw files in DATA_RAW_PATH to enable these
    optional_cogs = await _convert_optional_float32_layers()

    return DerivedLayers(
        ndvi=ndvi_path,
        ndwi=ndwi_path,
        dtm_cog=dtm_cog_path,
        building_height=building_height_path,
        lst_cog=lst_cog_path,
        optional_cogs=optional_cogs,
    )


async def _convert_optional_float32_layers() -> dict:
    """
    Convert any pre-existing raw float32 layers to uint8 COG.

    These layers (DSM, NDBI, Imperviousness, Albedo) have no automated download
    source and must be placed manually in DATA_RAW_PATH.

    Returns:
        Dict mapping layer label to output COG path (only for layers that exist)
    """
    candidates = [
        ("dsm.tif",            "dsm_brussels_2024.tif",            "DSM"),
        ("ndbi.tif",           "ndbi_brussels_2024.tif",           "NDBI"),
        ("imperviousness.tif", "imperviousness_brussels_2024.tif", "Imperviousness"),
        ("albedo.tif",         "albedo_brussels_2024.tif",         "Albedo"),
    ]
    result = {}
    for raw_name, cog_name, label in candidates:
        raw_file = DATA_RAW_PATH / raw_name
        cog_file = DATA_PROCESSED_PATH / cog_name
        if raw_file.exists():
            ingestion_status["progress"] = f"Converting {label} to COG..."
            await run_if_missing(cog_file, process_float32_cog, str(raw_file), str(cog_file))
            result[label] = cog_file
        else:
            logger.info(f"Optional layer '{label}' not found at {raw_file} — skipping")
    return result


# ── Phase 4: Register layers in Orion-LD ─────────────────────────────────────

async def _register_all_layers(sources: SourceData, derived: DerivedLayers) -> list[str]:
    """
    Upsert every layer as a GeoSpatialLayer entity in Orion-LD.

    Returns:
        List of layer_type strings for layers that were successfully registered
    """
    layers = _build_layer_list(sources, derived)
    registered = []
    for layer in layers:
        try:
            await orion_client.create_or_update_layer(layer)
            registered.append(layer.layer_type)
            logger.info(f"Registered: {layer.layer_type}")
        except Exception as e:
            logger.error(f"Failed to register {layer.layer_type}: {e}")
    return registered


def _build_layer_list(sources: SourceData, derived: DerivedLayers) -> list[GeoSpatialLayer]:
    """Assemble the full list of GeoSpatialLayer objects to register."""
    layers = [
        GeoSpatialLayer(layer_type="RGB",            name="RGB Brussels 2024",             spectral_range="RGB",       file_path=str(sources.rgb),            resolution=40),
        GeoSpatialLayer(layer_type="NIR",            name="NIR Brussels 2024",             spectral_range="NIR",       file_path=str(sources.nir),            resolution=40),
        GeoSpatialLayer(layer_type="NDVI",           name="NDVI Brussels 2024",            spectral_range="computed",  file_path=str(derived.ndvi),           resolution=40),
        GeoSpatialLayer(layer_type="NDWI",           name="NDWI Brussels 2024",            spectral_range="computed",  file_path=str(derived.ndwi),           resolution=40),
        GeoSpatialLayer(layer_type="DTM",            name="DTM Brussels 2021",             spectral_range="elevation", file_path=str(derived.dtm_cog),        resolution=100),
        GeoSpatialLayer(layer_type="BuildingHeight", name="Building Height Brussels 2024", spectral_range="elevation", file_path=str(derived.building_height), resolution=40),
    ]

    if derived.lst_cog and derived.lst_cog.exists():
        layers.append(
            GeoSpatialLayer(layer_type="LST", name="LST Brussels 2024", spectral_range="temperature", file_path=str(derived.lst_cog), resolution=40)
        )

    for label, cog_path in derived.optional_cogs.items():
        if cog_path.exists():
            layers.append(GeoSpatialLayer(
                layer_type=label,
                name=f"{label} Brussels 2024",
                spectral_range="elevation" if label == "DSM" else "computed",
                file_path=str(cog_path),
                resolution=100 if label == "DSM" else 40,
            ))

    return layers


# ── Pipeline entry point ──────────────────────────────────────────────────────

async def run_ingestion_pipeline(rgb_url: str, nir_url: str, dtm_url: str, buildings_url: str) -> None:
    """
    Execute the full geospatial data ingestion pipeline.

    Called as a FastAPI background task. Progress is tracked in
    ingestion_status and exposed via the /status endpoint.
    """
    global ingestion_status
    ingestion_status = {"running": True, "progress": "Starting ingestion...", "layers_created": []}

    try:
        # Step 1- Download sources from given URLs
        sources = await _download_all_sources(rgb_url, nir_url, dtm_url, buildings_url)
        # Step 2- Build internal overviews on raw rasters for better WMS performance in GeoServer
        await _build_source_overviews(sources)
        # Step 3- Compute derived layers (NDVI, NDWI, DTM, building heights, optional layers)
        derived = await _compute_derived_layers(sources)
        # Step 4- Register every layer as a GeoSpatialLayer entity in Orion-LD
        ingestion_status["progress"] = "Registering layers in Orion-LD..."
        ingestion_status["layers_created"] = await _register_all_layers(sources, derived)

        ingestion_status["progress"] = "Ingestion complete!"
        logger.info("Ingestion pipeline completed successfully")

    except Exception as e:
        logger.error(f"Ingestion pipeline failed: {e}")
        ingestion_status["progress"] = f"Error: {e}"
    finally:
        ingestion_status["running"] = False
