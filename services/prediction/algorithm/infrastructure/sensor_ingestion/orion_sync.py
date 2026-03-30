"""
Orion-LD sensor sync — converts SensorReadings into NGSI-LD entities
and upserts them into the Orion context broker.

Entity model:
    id:   urn:ngsi-ld:TemperatureSensor:{provider}:{station_id}
    type: TemperatureSensor

Each sensor becomes one persistent entity in Orion that gets updated
on every sync cycle with the latest measurement values.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import re

from algorithm.infrastructure.orion_client import OrionClient, OrionError
from algorithm.infrastructure.sensor_ingestion.base_provider import BaseSensorProvider
from algorithm.infrastructure.sensor_ingestion.models import SensorReading

logger = logging.getLogger(__name__)

ENTITY_TYPE = "TemperatureSensor"
MAX_RETRIES = 2
RETRY_DELAY = 1.0  # seconds


class SensorSyncService:
    """
    Orchestrates periodic sensor data ingestion from multiple providers
    into Orion-LD.

    Parameters
    ----------
    providers : list[BaseSensorProvider]
        Registered sensor data adapters.
    orion_client : OrionClient
        Client for upserting NGSI-LD entities.
    """

    def __init__(
        self,
        providers: list[BaseSensorProvider],
        orion_client: OrionClient,
    ) -> None:
        self._providers = providers
        self._orion = orion_client
        self._latest_readings: list[SensorReading] = []
        self._last_sync: str | None = None
        self._sync_count: int = 0

    @property
    def latest_readings(self) -> list[SensorReading]:
        """Most recent readings from the last successful sync."""
        return list(self._latest_readings)

    @property
    def status(self) -> dict[str, Any]:
        return {
            "last_sync": self._last_sync,
            "sync_count": self._sync_count,
            "providers": [p.provider_name for p in self._providers],
            "sensor_count": len(self._latest_readings),
        }

    # ── One-shot sync ─────────────────────────────────────────────────

    async def sync_all(self) -> list[SensorReading]:
        """
        Fetch readings from every provider and upsert into Orion.

        Returns the list of successfully synced readings.
        """
        all_readings: list[SensorReading] = []

        for provider in self._providers:
            try:
                readings = await provider.fetch_readings()
                all_readings.extend(readings)
            except Exception as exc:
                logger.error(
                    f"Provider '{provider.provider_name}' failed: {exc}",
                    exc_info=True,
                )

        # Upsert each reading into Orion
        synced: list[SensorReading] = []
        for reading in all_readings:
            entity = _build_entity(reading)
            try:
                await self._upsert_with_retry(entity)
                synced.append(reading)
            except OrionError as exc:
                logger.error(
                    f"Orion upsert failed for {entity['id']}: {exc}"
                )

        self._latest_readings = synced
        self._last_sync = datetime.now(timezone.utc).isoformat()
        self._sync_count += 1

        logger.info(
            f"Sensor sync complete: {len(synced)}/{len(all_readings)} "
            f"sensors published to Orion"
        )
        return synced

    async def _upsert_with_retry(self, entity: dict) -> str:
        """Upsert with exponential backoff on transient errors."""
        last_exc = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                return await self._orion.upsert_entity(entity)
            except OrionError as exc:
                last_exc = exc
                if attempt < MAX_RETRIES:
                    delay = RETRY_DELAY * (2 ** attempt)
                    logger.warning(
                        f"Orion upsert retry {attempt + 1}/{MAX_RETRIES} "
                        f"for {entity['id']} in {delay}s"
                    )
                    await asyncio.sleep(delay)
        raise last_exc  # type: ignore[misc]

    # ── Periodic background loop ──────────────────────────────────────

    async def run_periodic(self, interval_seconds: float) -> None:
        """
        Run sync_all() in an infinite loop.

        Designed to be launched as an ``asyncio.Task`` from the FastAPI lifespan.
        Catches all exceptions to prevent the loop from dying.
        """
        logger.info(
            f"Sensor sync loop started (interval={interval_seconds}s, "
            f"providers={[p.provider_name for p in self._providers]})"
        )
        # Initial sync immediately
        await self._safe_sync()

        while True:
            await asyncio.sleep(interval_seconds)
            await self._safe_sync()

    async def _safe_sync(self) -> None:
        """Sync with full exception guard."""
        try:
            await self.sync_all()
        except Exception as exc:
            logger.error(f"Sensor sync cycle failed: {exc}", exc_info=True)


# ── Helpers ───────────────────────────────────────────────────────────────


def _normalize_iso8601(raw: str | None) -> str:
    """
    Return an Orion-LD-safe ``YYYY-MM-DDTHH:MM:SSZ`` timestamp.

    Orion-LD rejects anything that isn't strict ISO8601 ending with ``Z``.
    Falls back to ``datetime.now(UTC)`` when the input is empty or unparseable.
    """
    _utc_now = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if not raw or not raw.strip():
        return _utc_now()

    raw = raw.strip()
    try:
        # Handle common formats from VLINDER / Mooncake:
        #   "2026-03-26T15:30:00.000Z"
        #   "2026-03-26T15:30:00Z"
        #   "2026-03-26T15:30:00+00:00"
        #   "2026-03-26 15:30:00"   (space instead of T)
        #   epoch millis as string  (e.g. "1711461000000")

        # Epoch millis (13 digits)
        if re.fullmatch(r"\d{13}", raw):
            dt = datetime.fromtimestamp(int(raw) / 1000, tz=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Epoch seconds (10 digits)
        if re.fullmatch(r"\d{10}", raw):
            dt = datetime.fromtimestamp(int(raw), tz=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Replace space separator with T
        normalized = raw.replace(" ", "T")

        # Strip fractional seconds (Orion doesn't need them)
        normalized = re.sub(r"\.\d+", "", normalized)

        # Strip timezone offset and replace with Z
        normalized = re.sub(r"[+-]\d{2}:\d{2}$", "", normalized)
        if not normalized.endswith("Z"):
            normalized += "Z"

        # Validate by parsing
        datetime.strptime(normalized, "%Y-%m-%dT%H:%M:%SZ")
        return normalized

    except (ValueError, OverflowError, OSError):
        logger.warning(f"Unparseable timestamp '{raw}', using UTC now")
        return _utc_now()


# ── NGSI-LD entity builder ────────────────────────────────────────────────


def _build_entity(reading: SensorReading) -> dict[str, Any]:
    """
    Convert a SensorReading into an NGSI-LD entity payload.

    Entity ID: urn:ngsi-ld:TemperatureSensor:{provider}:{station_id}
    """
    entity_id = f"urn:ngsi-ld:{ENTITY_TYPE}:{reading.provider}:{reading.station_id}"

    entity: dict[str, Any] = {
        "id": entity_id,
        "type": ENTITY_TYPE,
        "provider": {
            "type": "Property",
            "value": reading.provider,
        },
        "stationId": {
            "type": "Property",
            "value": reading.station_id,
        },
        "stationName": {
            "type": "Property",
            "value": reading.station_name,
        },
        "status": {
            "type": "Property",
            "value": reading.status,
        },
        "fallback": {
            "type": "Property",
            "value": reading.fallback,
        },
    }

    # Temporal properties — include observedAt for time-series tracking
    # Orion-LD requires strict ISO8601: YYYY-MM-DDTHH:MM:SS[.fff]Z
    observed_at = _normalize_iso8601(reading.observed_at)

    if reading.temperature is not None:
        entity["temperature"] = {
            "type": "Property",
            "value": reading.temperature,
            "observedAt": observed_at,
        }

    if reading.humidity is not None:
        entity["humidity"] = {
            "type": "Property",
            "value": reading.humidity,
            "observedAt": observed_at,
        }

    if reading.pressure is not None:
        entity["pressure"] = {
            "type": "Property",
            "value": reading.pressure,
            "observedAt": observed_at,
        }

    if reading.wind_speed is not None:
        entity["windSpeed"] = {
            "type": "Property",
            "value": reading.wind_speed,
            "observedAt": observed_at,
        }

    if reading.wind_direction is not None:
        entity["windDirection"] = {
            "type": "Property",
            "value": reading.wind_direction,
            "observedAt": observed_at,
        }

    if reading.wind_gust is not None:
        entity["windGust"] = {
            "type": "Property",
            "value": reading.wind_gust,
            "observedAt": observed_at,
        }

    if reading.rain_intensity is not None:
        entity["rainIntensity"] = {
            "type": "Property",
            "value": reading.rain_intensity,
            "observedAt": observed_at,
        }

    # GeoProperty — location as GeoJSON Point
    if reading.latitude is not None and reading.longitude is not None:
        entity["location"] = {
            "type": "GeoProperty",
            "value": {
                "type": "Point",
                "coordinates": [reading.longitude, reading.latitude],
            },
        }

    return entity
