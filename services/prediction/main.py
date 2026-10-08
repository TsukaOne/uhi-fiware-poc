"""
Application entry point — composition root only.

Wires config → infrastructure → application → API. No business logic here.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from algorithm.api.sensor_router import router as sensor_router
from algorithm.api.zone_router import router as zone_router
from algorithm.application.zone_predictor import ZonePredictor
from algorithm.config import settings
from algorithm.infrastructure.orion_client import OrionClient
from algorithm.infrastructure.sensor_ingestion.orion_sync import SensorSyncService
from algorithm.infrastructure.sensor_ingestion.sensors_community_provider import SensorsCommunityProvider
from algorithm.infrastructure.sensor_ingestion.vlinder_provider import VlinderProvider

logging.basicConfig(level=logging.INFO)

orion_client = OrionClient(settings)

zone_predictor = ZonePredictor(settings)

vlinder_provider = VlinderProvider(station_ids=settings.vlinder_station_ids)
sensors_community_provider = SensorsCommunityProvider(
    lat=settings.sc_center_lat,
    lon=settings.sc_center_lon,
    radius_km=settings.sc_radius_km,
)
sensor_sync_service = SensorSyncService(
    providers=[vlinder_provider, sensors_community_provider],
    orion_client=orion_client,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    missing_files = [path for path in settings.required_files if not path.exists()]
    if missing_files:
        raise RuntimeError(f"Missing data files: {missing_files}")

    sync_task = asyncio.create_task(
        sensor_sync_service.run_periodic(settings.sensor_sync_interval)
    )
    yield
    sync_task.cancel()


app = FastAPI(
    title="UHI Prediction Service",
    description="Urban Heat Island prediction on user-drawn zones.",
    version="3.0.0",
    lifespan=lifespan,
)

app.include_router(zone_router)
app.include_router(sensor_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "prediction"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
