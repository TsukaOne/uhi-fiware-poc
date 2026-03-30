"""
VLINDER / Mooncake adapter — fetches real-time measurements from
multiple VLINDER weather stations and normalizes them into SensorReadings.

Station metadata (coordinates, name) is fetched once on first sync
and cached for the lifetime of the process.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx

from algorithm.infrastructure.sensor_ingestion.base_provider import BaseSensorProvider
from algorithm.infrastructure.sensor_ingestion.models import SensorReading, StationMetadata

logger = logging.getLogger(__name__)

MOONCAKE_BASE_URL = "https://mooncake.ugent.be/api"
HTTP_TIMEOUT = 15.0
MAX_CONCURRENT = 4  # limit parallel requests to Mooncake


class VlinderProvider(BaseSensorProvider):
    """
    Adapter for the UGent VLINDER / Mooncake weather station network.

    Parameters
    ----------
    station_ids : list[str]
        Mooncake station IDs to monitor (e.g. ["bPlA09QS8LkV82rkdlAphY1d", ...]).
    """

    def __init__(self, station_ids: list[str]) -> None:
        self._station_ids = station_ids
        self._metadata_cache: dict[str, StationMetadata] = {}
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    @property
    def provider_name(self) -> str:
        return "vlinder"

    async def fetch_readings(self) -> list[SensorReading]:
        """Fetch latest reading from every configured VLINDER station."""
        # Ensure metadata is loaded (coordinates, names)
        await self._ensure_metadata()

        tasks = [self._fetch_one(sid) for sid in self._station_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        readings: list[SensorReading] = []
        for sid, result in zip(self._station_ids, results):
            if isinstance(result, Exception):
                logger.warning(f"VLINDER station {sid}: fetch failed — {result}")
                continue
            if result is not None:
                readings.append(result)

        logger.info(
            f"VLINDER: fetched {len(readings)}/{len(self._station_ids)} stations"
        )
        return readings

    # ── Single-station fetch ──────────────────────────────────────────

    async def _fetch_one(self, station_id: str) -> Optional[SensorReading]:
        """Fetch the latest measurement for one station."""
        url = f"{MOONCAKE_BASE_URL}/measurements/{station_id}"

        async with self._semaphore:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(url)
                resp.raise_for_status()

        data = resp.json()
        if not data:
            logger.warning(f"VLINDER station {station_id}: empty response")
            return None

        # API returns an array of measurements; take the most recent
        latest = data[-1] if isinstance(data, list) else data

        meta = self._metadata_cache.get(station_id)
        name = self._format_name(meta) if meta else station_id

        return SensorReading(
            provider="vlinder",
            station_id=station_id,
            station_name=name,
            temperature=_float_or_none(latest.get("temp")),
            humidity=_float_or_none(latest.get("humidity")),
            pressure=_float_or_none(latest.get("pressure")),
            wind_speed=_float_or_none(latest.get("windSpeed")),
            wind_direction=_float_or_none(latest.get("windDirection")),
            wind_gust=_float_or_none(latest.get("windGust")),
            rain_intensity=_float_or_none(latest.get("rainIntensity")),
            latitude=meta.latitude if meta else None,
            longitude=meta.longitude if meta else None,
            observed_at=latest.get("time", ""),
            status=latest.get("status", "Unknown"),
        )

    # ── Metadata (fetched once, cached) ───────────────────────────────

    async def _ensure_metadata(self) -> None:
        """Fetch station metadata for any station not yet in cache."""
        missing = [
            sid for sid in self._station_ids
            if sid not in self._metadata_cache
        ]
        if not missing:
            return

        logger.info(f"VLINDER: fetching metadata for {len(missing)} station(s)")
        tasks = [self._fetch_station_meta(sid) for sid in missing]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for sid, result in zip(missing, results):
            if isinstance(result, Exception):
                logger.warning(f"VLINDER station {sid}: metadata fetch failed — {result}")
            elif result is not None:
                self._metadata_cache[sid] = result

    async def _fetch_station_meta(self, station_id: str) -> StationMetadata:
        """GET /api/stations/{station_id} → StationMetadata."""
        url = f"{MOONCAKE_BASE_URL}/stations/{station_id}"

        async with self._semaphore:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(url)
                resp.raise_for_status()

        info = resp.json()
        coords = info.get("coordinates", {})

        return StationMetadata(
            station_id=station_id,
            name=info.get("name", ""),
            given_name=info.get("given_name", ""),
            city=info.get("city", ""),
            latitude=_float_or_none(coords.get("latitude")),
            longitude=_float_or_none(coords.get("longitude")),
        )

    @staticmethod
    def _format_name(meta: StationMetadata) -> str:
        """Build a human-readable station name from metadata."""
        parts = [meta.name]
        if meta.given_name:
            parts.append(f"({meta.given_name})")
        if meta.city:
            parts.append(f"— {meta.city}")
        return " ".join(parts)


def _float_or_none(val) -> Optional[float]:
    """Safely convert a value to float, returning None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
