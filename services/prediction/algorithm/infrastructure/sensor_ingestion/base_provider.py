"""
Abstract base class for sensor data providers.

Every new data source (VLINDER, Sensors.community, IRM, …) implements
this interface so the sync orchestrator can treat them uniformly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from algorithm.infrastructure.sensor_ingestion.models import SensorReading


class BaseSensorProvider(ABC):
    """Adapter interface that all sensor providers must implement."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique short identifier used in entity IDs (e.g. 'vlinder')."""

    @abstractmethod
    async def fetch_readings(self) -> list[SensorReading]:
        """
        Fetch the latest readings from all configured stations.

        Implementations should:
        - Handle per-station failures gracefully (log & skip).
        - Return only successfully fetched readings.
        - Set ``fallback=True`` on readings that used cached data.
        """
