"""
Normalized data models for multi-provider sensor ingestion.

All providers (VLINDER, Sensors.community, IRM, …) produce SensorReading
instances that share the same structure regardless of the upstream API format.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SensorReading:
    """A single sensor observation normalized across providers."""

    provider: str               # e.g. "vlinder", "sensors_community", "irm"
    station_id: str             # raw provider-specific station identifier
    station_name: str           # human-readable name
    temperature: Optional[float] = None   # °C
    humidity: Optional[float] = None      # %
    pressure: Optional[float] = None      # hPa
    wind_speed: Optional[float] = None    # m/s
    wind_direction: Optional[float] = None  # degrees
    wind_gust: Optional[float] = None     # m/s
    rain_intensity: Optional[float] = None  # mm/h
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    observed_at: str = ""       # ISO 8601 timestamp
    status: str = "Ok"
    fallback: bool = False      # True when using cached / default values


@dataclass
class StationMetadata:
    """Cached station metadata (fetched once, rarely changes)."""

    station_id: str
    name: str
    given_name: str = ""
    city: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
