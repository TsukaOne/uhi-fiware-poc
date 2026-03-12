"""
VLINDER / Mooncake client — fetches real-time temperature from
the UGent weather station network.

Caches the last valid reading in memory (TTL configurable).
Falls back to cached value then to a default if the API is unreachable.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

MOONCAKE_BASE_URL = "https://mooncake.ugent.be/api"


@dataclass
class TBaseReading:
    value: float
    station_id: str
    station_name: str
    timestamp: str
    fallback: bool = False


@dataclass
class _CacheEntry:
    reading: TBaseReading
    fetched_at: float = field(default_factory=time.monotonic)


class VlinderClient:
    """Thin async client around the Mooncake measurements API."""

    def __init__(
        self,
        station_id: str,
        default_temp: float = 15.0,
        cache_ttl_seconds: float = 600.0,
        timeout: float = 10.0,
    ) -> None:
        self._station_id = station_id
        self._default_temp = default_temp
        self._cache_ttl = cache_ttl_seconds
        self._timeout = timeout
        self._cache: Optional[_CacheEntry] = None

    async def get_t_base(self) -> TBaseReading:
        """
        Return the latest temperature for the configured reference station.

        Priority:
          1. Fresh API call (if cache expired or absent)
          2. Stale cache (if API fails) → fallback=True
          3. Default value (if no cache at all) → fallback=True
        """
        if self._cache and not self._is_expired(self._cache):
            return self._cache.reading

        try:
            reading = await self._fetch_latest()
            self._cache = _CacheEntry(reading=reading)
            return reading
        except Exception as exc:
            logger.warning(f"VLINDER API error: {exc}")
            if self._cache:
                stale = self._cache.reading
                return TBaseReading(
                    value=stale.value,
                    station_id=stale.station_id,
                    station_name=stale.station_name,
                    timestamp=stale.timestamp,
                    fallback=True,
                )
            return TBaseReading(
                value=self._default_temp,
                station_id=self._station_id,
                station_name="default",
                timestamp="",
                fallback=True,
            )

    async def _fetch_latest(self) -> TBaseReading:
        """Hit the Mooncake measurements endpoint for one station."""
        url = f"{MOONCAKE_BASE_URL}/measurements"
        params = {"stationId": self._station_id}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()

        data = resp.json()
        if not data:
            raise ValueError("Empty response from Mooncake API")

        # The API returns an array; take the most recent entry
        latest = data[-1] if isinstance(data, list) else data
        temp = latest.get("temp")
        if temp is None:
            raise ValueError(f"No 'temp' field in measurement: {latest}")

        station_resp = await self._fetch_station_name()

        return TBaseReading(
            value=float(temp),
            station_id=self._station_id,
            station_name=station_resp,
            timestamp=latest.get("time", ""),
            fallback=False,
        )

    async def _fetch_station_name(self) -> str:
        """Resolve a human-readable name for the station (cached in reading)."""
        if self._cache and self._cache.reading.station_name != "default":
            return self._cache.reading.station_name
        try:
            url = f"{MOONCAKE_BASE_URL}/stations/{self._station_id}"
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url)
                resp.raise_for_status()
            info = resp.json()
            given = info.get("given_name", "")
            name = info.get("name", "")
            return f"{name} ({given})" if given else name
        except Exception:
            return self._station_id

    def _is_expired(self, entry: _CacheEntry) -> bool:
        return (time.monotonic() - entry.fetched_at) > self._cache_ttl
