"""
Sensor cache — keeps the latest readings of every provider in memory.
"""
from __future__ import annotations

import asyncio
import logging

from algorithm.infrastructure.sensor_ingestion.base_provider import BaseSensorProvider
from algorithm.infrastructure.sensor_ingestion.models import SensorReading

logger = logging.getLogger(__name__)


class SensorCache:

    def __init__(self, providers: list[BaseSensorProvider]) -> None:
        self._providers = providers
        self.readings: list[SensorReading] = []

    async def refresh(self) -> None:
        readings: list[SensorReading] = []
        for provider in self._providers:
            try:
                readings.extend(await provider.fetch_readings())
            except Exception:
                logger.exception(f"Sensor provider '{provider.provider_name}' failed")
        self.readings = readings
        logger.info(f"Sensor cache refreshed: {len(readings)} readings")

    async def run_periodic(self, interval_seconds: float) -> None:
        while True:
            await self.refresh()
            await asyncio.sleep(interval_seconds)
