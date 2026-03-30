"""
Sensor API Router — exposes multi-provider sensor data endpoints.

All sensor data flows through Orion-LD. These endpoints provide
convenient access to the latest cached readings and manual sync control.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from algorithm.infrastructure.sensor_ingestion.orion_sync import SensorSyncService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sensors", tags=["sensors"])


# ── Response models ───────────────────────────────────────────────────────

class SensorResponse(BaseModel):
    provider: str
    station_id: str
    station_name: str
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pressure: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_direction: Optional[float] = None
    wind_gust: Optional[float] = None
    rain_intensity: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    observed_at: str = ""
    status: str = "Ok"
    fallback: bool = False


class SensorListResponse(BaseModel):
    sensors: list[SensorResponse]
    count: int


class SyncStatusResponse(BaseModel):
    last_sync: Optional[str] = None
    sync_count: int
    providers: list[str]
    sensor_count: int


class SyncResultResponse(BaseModel):
    synced: int
    total: int
    sensors: list[SensorResponse]


# ── Dependency injection ──────────────────────────────────────────────────

def _get_sync_service() -> SensorSyncService:
    from main import sensor_sync_service
    return sensor_sync_service


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("", response_model=SensorListResponse)
async def list_sensors(
    provider: Optional[str] = None,
    service: SensorSyncService = Depends(_get_sync_service),
):
    """Return all latest cached sensor readings, optionally filtered by provider."""
    readings = service.latest_readings
    if provider:
        readings = [r for r in readings if r.provider == provider]

    sensors = [SensorResponse(**r.__dict__) for r in readings]
    return SensorListResponse(sensors=sensors, count=len(sensors))


@router.get("/status", response_model=SyncStatusResponse)
async def sync_status(
    service: SensorSyncService = Depends(_get_sync_service),
):
    """Return the current sync service status."""
    return SyncStatusResponse(**service.status)


@router.post("/sync", response_model=SyncResultResponse)
async def trigger_sync(
    service: SensorSyncService = Depends(_get_sync_service),
):
    """Manually trigger a sync cycle across all providers."""
    readings = await service.sync_all()
    sensors = [SensorResponse(**r.__dict__) for r in readings]
    return SyncResultResponse(
        synced=len(sensors),
        total=len(sensors),
        sensors=sensors,
    )
