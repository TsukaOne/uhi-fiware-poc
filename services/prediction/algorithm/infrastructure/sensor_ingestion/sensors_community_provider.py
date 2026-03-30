"""
Sensors.community adapter — fetches real-time temperature/humidity measurements
from the open sensor network within a geographic area.

API docs: https://github.com/opendata-stuttgart/meta/wiki/EN-APIs
Endpoint:  https://data.sensor.community/airrohr/v1/filter/area={lat},{lon},{radius}

All sensor types reporting temperature are included (BME280, DHT22, BMP180, etc.).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from algorithm.infrastructure.sensor_ingestion.base_provider import BaseSensorProvider
from algorithm.infrastructure.sensor_ingestion.models import SensorReading

logger = logging.getLogger(__name__)

API_BASE = "https://data.sensor.community/airrohr/v1"
HTTP_TIMEOUT = 30.0
USER_AGENT = "uhi-fiware-poc/1.0 (https://github.com/uhi-fiware-poc)"


class SensorsCommunityProvider(BaseSensorProvider):
    """
    Adapter for the Sensors.community (formerly Luftdaten) open sensor network.

    Fetches all BME280 sensors within a given radius of a center point.

    Parameters
    ----------
    lat : float
        Center latitude (e.g. 50.83653 for Brussels).
    lon : float
        Center longitude (e.g. 4.38047 for Brussels).
    radius_km : float
        Search radius in kilometers (e.g. 9.91 for greater Brussels).
    """

    def __init__(self, lat: float, lon: float, radius_km: float) -> None:
        self._lat = lat
        self._lon = lon
        self._radius_km = radius_km

    @property
    def provider_name(self) -> str:
        return "sensors_community"

    async def fetch_readings(self) -> list[SensorReading]:
        """Fetch all sensor readings with temperature within the configured area."""
        url = f"{API_BASE}/filter/area={self._lat},{self._lon},{self._radius_km}"

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(
                    url,
                    headers={"User-Agent": USER_AGENT},
                )
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error(f"Sensors.community API error: {exc}")
            return []

        raw_sensors = resp.json()
        if not isinstance(raw_sensors, list):
            logger.warning("Sensors.community: unexpected response format")
            return []

        readings: list[SensorReading] = []
        seen_ids: set[str] = set()

        for entry in raw_sensors:
            try:
                reading = self._parse_entry(entry)
                if reading and reading.station_id not in seen_ids:
                    seen_ids.add(reading.station_id)
                    readings.append(reading)
            except Exception as exc:
                logger.debug(f"Sensors.community: skipping entry — {exc}")

        logger.info(
            f"Sensors.community: fetched {len(readings)} sensors "
            f"within {self._radius_km}km of ({self._lat}, {self._lon})"
        )
        return readings

    def _parse_entry(self, entry: dict) -> Optional[SensorReading]:
        """Parse a single sensor entry from the API response."""
        sensor_info = entry.get("sensor", {})
        location = entry.get("location", {})
        sensor_data = entry.get("sensordatavalues", [])

        sensor_id = str(sensor_info.get("id", ""))
        if not sensor_id:
            return None

        lat = _float_or_none(location.get("latitude"))
        lon = _float_or_none(location.get("longitude"))
        if lat is None or lon is None:
            return None

        # Parse sensor data values into a dict
        values: dict[str, float] = {}
        for item in sensor_data:
            key = item.get("value_type", "")
            val = _float_or_none(item.get("value"))
            if key and val is not None:
                values[key] = val

        temperature = values.get("temperature")
        if temperature is None:
            return None

        # Basic sanity check — reject obviously broken readings
        if temperature < -50 or temperature > 70:
            return None

        timestamp = entry.get("timestamp", "")
        # Sensors.community timestamps are in format "2026-03-27 15:30:00"
        observed_at = timestamp.replace(" ", "T") + "Z" if timestamp else ""

        return SensorReading(
            provider="sensors_community",
            station_id=sensor_id,
            station_name=f"SC-{sensor_id}",
            temperature=temperature,
            humidity=_float_or_none_from_dict(values, "humidity"),
            pressure=_pressure_hpa(values),
            latitude=lat,
            longitude=lon,
            observed_at=observed_at,
            status="Ok",
        )


def _float_or_none(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _float_or_none_from_dict(d: dict, key: str) -> Optional[float]:
    return _float_or_none(d.get(key))


def _pressure_hpa(values: dict) -> Optional[float]:
    """Sensors.community reports pressure in Pa; convert to hPa."""
    raw = _float_or_none(values.get("pressure"))
    if raw is None:
        return None
    # If value > 10000, it's in Pa — convert to hPa
    return raw / 100.0 if raw > 10000 else raw
