"""
Sensor API Router — serves the latest sensor readings kept in memory.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from algorithm.infrastructure.sensor_ingestion.sensor_cache import SensorCache

router = APIRouter(prefix="/sensors", tags=["sensors"])


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


def _get_sensor_cache() -> SensorCache:
    from main import sensor_cache
    return sensor_cache


@router.get("", response_model=SensorListResponse)
async def list_sensors(cache: SensorCache = Depends(_get_sensor_cache)):
    sensors = [SensorResponse(**reading.__dict__) for reading in cache.readings]
    return SensorListResponse(sensors=sensors, count=len(sensors))
