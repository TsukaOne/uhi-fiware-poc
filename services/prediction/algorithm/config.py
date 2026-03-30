"""
Centralised configuration.

Every environment variable consumed by the prediction service
is declared here exactly once, with its type and default value.
"""
from __future__ import annotations

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings

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

    # ── Service identity ──────────────────────────────────────────────
    self_url: str = Field(default="http://prediction:8000", alias="SELF_URL")
    prediction_subscription_id: str = Field(
        default="urn:ngsi-ld:Subscription:uhi-prediction-trigger",
        alias="PREDICTION_SUBSCRIPTION_ID",
    )

    # ── File paths ────────────────────────────────────────────────────
    output_path: Path = Field(default=Path("/data/processed"), alias="DATA_PROCESSED_PATH")
    model_path: Path = Field(default=Path("/data/models"), alias="MODEL_PATH")
    cache_path: Path = Field(default=Path("/data/cache"), alias="CACHE_PATH")

    # ── Input entity IDs ──────────────────────────────────────────────
    ndvi_entity_id: str = Field(
        default="urn:ngsi-ld:GeoSpatialLayer:NDVI:brussels:2024",
        alias="NDVI_ENTITY_ID",
    )
    ndwi_entity_id: str = Field(
        default="urn:ngsi-ld:GeoSpatialLayer:NDWI:brussels:2024",
        alias="NDWI_ENTITY_ID",
    )
    dtm_entity_id: str = Field(
        default="urn:ngsi-ld:GeoSpatialLayer:DTM:brussels:2024",
        alias="DTM_ENTITY_ID",
    )
    building_height_entity_id: str = Field(
        default="urn:ngsi-ld:GeoSpatialLayer:BuildingHeight:brussels:2024",
        alias="BUILDING_HEIGHT_ENTITY_ID",
    )
    lst_entity_id: str = Field(
        default="urn:ngsi-ld:GeoSpatialLayer:LST:brussels:2024",
        alias="LST_ENTITY_ID",
    )
    dsm_entity_id: str = Field(
        default="urn:ngsi-ld:GeoSpatialLayer:DSM:brussels:2024",
        alias="DSM_ENTITY_ID",
    )
    imperviousness_entity_id: str = Field(
        default="urn:ngsi-ld:GeoSpatialLayer:Imperviousness:brussels:2024",
        alias="IMPERVIOUSNESS_ENTITY_ID",
    )
    ndbi_entity_id: str = Field(
        default="urn:ngsi-ld:GeoSpatialLayer:NDBI:brussels:2024",
        alias="NDBI_ENTITY_ID",
    )
    albedo_entity_id: str = Field(
        default="urn:ngsi-ld:GeoSpatialLayer:Albedo:brussels:2024",
        alias="ALBEDO_ENTITY_ID",
    )

    # ── Rural reference point (row, col) for LST baseline ─────────────
    rural_point_row: int = Field(default=15561, alias="RURAL_POINT_ROW")
    rural_point_col: int = Field(default=12526, alias="RURAL_POINT_COL")

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

    # ── Training hyperparameter defaults ──────────────────────────────
    training_sample_rate: float = Field(default=0.005, alias="TRAINING_SAMPLE_RATE")
    training_n_estimators: int = Field(default=500, alias="TRAINING_N_ESTIMATORS")
    training_max_depth: int = Field(default=8, alias="TRAINING_MAX_DEPTH")
    training_learning_rate: float = Field(default=0.05, alias="TRAINING_LEARNING_RATE")
    training_use_gpu: bool = Field(default=True, alias="TRAINING_USE_GPU")

    @property
    def rural_point(self) -> tuple[int, int]:
        return (self.rural_point_row, self.rural_point_col)

    @property
    def all_layer_entity_ids(self) -> dict[str, str]:
        """Mapping layer_name → entity_id for all training layers."""
        return {
            "ndvi": self.ndvi_entity_id,
            "ndwi": self.ndwi_entity_id,
            "ndbi": self.ndbi_entity_id,
            "dtm": self.dtm_entity_id,
            "dsm": self.dsm_entity_id,
            "building_height": self.building_height_entity_id,
            "imperviousness": self.imperviousness_entity_id,
            "albedo": self.albedo_entity_id,
            "lst": self.lst_entity_id,
        }

    @property
    def prediction_layer_entity_ids(self) -> dict[str, str]:
        """Mapping layer_name → entity_id for the two prediction-trigger layers."""
        return {
            "ndvi": self.ndvi_entity_id,
            "ndwi": self.ndwi_entity_id,
        }

    model_config = {"populate_by_name": True, "env_file": ".env"}


# Module-level singleton to be imported and used everywhere in the service
settings = Settings()