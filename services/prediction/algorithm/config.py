"""
Centralised configuration.

Every environment variable consumed by the prediction service
is declared here exactly once, with its type and default value.
"""
from __future__ import annotations

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings

LAYER_FILES = {
    "ndvi": "ndvi_brussels_2024.tif",
    "ndwi": "ndwi_brussels_2024.tif",
    "ndbi": "ndbi_brussels_2024.tif",
    "dtm": "dtm_brussels_2021.tif",
    "dsm": "dsm_brussels_2024.tif",
    "building_height": "building_height_brussels.tif",
    "imperviousness": "imperviousness_brussels_2024.tif",
    "albedo": "albedo_brussels_2024.tif",
    "lst": "lst_cog_2024.tif",
}
UHI_HEATMAP_FILE = "uhi_xgb_heatmap_brussels_2024.tif"
MODEL_FILE = "xgb_uhi_latest.joblib"


class Settings(BaseSettings):
    """─
    All service settings resolved from environment variables at startup.
    Validated once by Pydantic.
    """

    # ── Orion-LD ────────────────────────────────────────────────────
    orion_url: str = Field(default="http://orion:1026", alias="ORION_URL")
    orion_timeout: float = Field(default=15.0, alias="ORION_TIMEOUT")
    ngsi_ld_context: str = Field(
        default="https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
        alias="NGSI_LD_CONTEXT",
    )

    # ── Data directories ──────────────────────────────────────────────
    processed_dir: Path = Field(default=Path("/data/processed"), alias="DATA_PROCESSED_PATH")
    models_dir: Path = Field(default=Path("/data/models"), alias="MODEL_PATH")

    # ── Multi-sensor ingestion ─────────────────────────────────────────
    vlinder_stations: str = Field(
        default=(
            "bPlA09QS8LkV82rkdlAphY1d,"  # VLINDER 97 — Ukkel KMI
            "5S5RGUTdmLFNGKiRqjGF8mMG,"  # VLINDER 95
            "q40fv0czc0GeoAblR0YK4WwG,"  # VLINDER 93
            "6M4Qz8B5farfKJjVtiKReZmQ,"  # VLINDER 74
            "xgRUxj1N6DiRKzekQqI4Z5Ns,"  # VLINDER 90
            "Ziocm4OqUjrp7W9988artyfN"   # VLINDER 96
        ),
        alias="VLINDER_STATIONS",
        description="Comma-separated Mooncake station IDs for multi-sensor ingestion",
    )
    sensor_sync_interval: float = Field(
        default=600.0,
        alias="SENSOR_SYNC_INTERVAL",
        description="Interval in seconds between sensor sync cycles (default: 10 min)",
    )

    # ── Sensors.community ────────────────────────────────────────────
    sc_center_lat: float = Field(
        default=50.83653, alias="SC_CENTER_LAT",
        description="Center latitude for Sensors.community area query",
    )
    sc_center_lon: float = Field(
        default=4.38047, alias="SC_CENTER_LON",
        description="Center longitude for Sensors.community area query",
    )
    sc_radius_km: float = Field(
        default=9.91, alias="SC_RADIUS_KM",
        description="Radius in km for Sensors.community area query",
    )

    @property
    def vlinder_station_ids(self) -> list[str]:
        """Parse the comma-separated station IDs into a list."""
        return [s.strip() for s in self.vlinder_stations.split(",") if s.strip()]

    @property
    def layer_paths(self) -> dict[str, Path]:
        return {name: self.processed_dir / file for name, file in LAYER_FILES.items()}

    @property
    def uhi_heatmap_path(self) -> Path:
        return self.processed_dir / UHI_HEATMAP_FILE

    @property
    def model_file(self) -> Path:
        return self.models_dir / MODEL_FILE

    @property
    def required_files(self) -> list[Path]:
        return [*self.layer_paths.values(), self.uhi_heatmap_path, self.model_file]

    model_config = {"populate_by_name": True, "env_file": ".env"}


# Module-level singleton to be imported and used everywhere in the service
settings = Settings()