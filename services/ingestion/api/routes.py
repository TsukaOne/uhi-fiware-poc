"""
HTTP route handlers.

Exposes four endpoints:
  GET  /health                 — liveness probe
  GET  /status                 — current pipeline progress
  GET  /layers                 — list all layers registered in Orion-LD
  POST /ingest/orthophotos     — trigger the ingestion pipeline
"""

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException

from api.models import IngestRequest, IngestResponse, LayerInfo
from config import DEFAULT_BUILDINGS_URL, DEFAULT_DTM_URL, DEFAULT_NIR_URL, DEFAULT_RGB_URL, ORION_URL
from fiware.client import OrionClient
from pipeline.run import ingestion_status, run_ingestion_pipeline

logger = logging.getLogger(__name__)

router = APIRouter()
orion_client = OrionClient(ORION_URL)


@router.get("/health")
async def health_check():
    """Liveness probe."""
    return {"status": "healthy", "service": "ingestion"}


@router.get("/status")
async def get_status():
    """Return the current pipeline state (running, progress, layers_created)."""
    return ingestion_status


@router.get("/layers", response_model=list[LayerInfo])
async def list_layers():
    """List all GeoSpatialLayer entities registered in Orion-LD."""
    try:
        layers = await orion_client.get_all_layers()
        return [
            LayerInfo(
                id=layer.get("id", ""),
                name=layer.get("name", {}).get("value", ""),
                layer_type=layer.get("layerType", {}).get("value", ""),
                file_path=layer.get("filePath", {}).get("value", ""),
                geoserver_layer=layer.get("geoserverLayer", {}).get("value", ""),
            )
            for layer in layers
        ]
    except Exception as e:
        logger.error(f"Failed to list layers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/orthophotos", response_model=IngestResponse)
async def ingest_orthophotos(
    background_tasks: BackgroundTasks,
    request: Optional[IngestRequest] = None,
):
    """
    Trigger the full ingestion pipeline in the background.

    All URL parameters are optional: omit them to use the environment defaults.
    Poll /status to follow progress.
    """
    if ingestion_status["running"]:
        raise HTTPException(status_code=409, detail="Ingestion already in progress")

   # Use request URLs if providedn - otherwise use environment defaults
    rgb_url = (request and request.rgb_url) or DEFAULT_RGB_URL
    nir_url = (request and request.nir_url) or DEFAULT_NIR_URL
    dtm_url = (request and request.dtm_url) or DEFAULT_DTM_URL
    buildings_url = (request and request.buildings_and_engineering_works_url) or DEFAULT_BUILDINGS_URL

    if not rgb_url or not nir_url:
        raise HTTPException(status_code=400, detail="RGB and NIR URLs are required")
    if not dtm_url:
        raise HTTPException(status_code=400, detail="DTM URL is required")
    if not buildings_url:
        raise HTTPException(status_code=400, detail="Buildings URL is required")

    logger.info(f"Ingestion requested — RGB={rgb_url}, NIR={nir_url}, DTM={dtm_url}")
    background_tasks.add_task(run_ingestion_pipeline, rgb_url, nir_url, dtm_url, buildings_url)

    return IngestResponse(
        status="started",
        message="Ingestion pipeline started in background",
        layers=[],
    )
