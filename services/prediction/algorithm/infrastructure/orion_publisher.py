"""
Orion Publisher — builds and registers result entities back into Orion-LD.

Single responsibility: construct NGSI-LD entity payloads for outputs
(predictions, trained models) and delegate persistence to OrionClient.

"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import rasterio
from rasterio.warp import transform_bounds

from algorithm.infrastructure.orion_client import OrionClient

logger = logging.getLogger(__name__)

 # Constants for entity IDs
_XGB_HEATMAP_ENTITY_ID = "urn:ngsi-ld:UHIHeatMap:XGBoost:brussels:2024"
_MODEL_ENTITY_ID = "urn:ngsi-ld:UHIModel:XGBoost:brussels:2024"


class OrionPublisher:
    """
    Publishes prediction and model artifacts as NGSI-LD entities.

    All three entity schemas (UHIHeatMap legacy, UHIHeatMap XGBoost, UHIModel)
    are built here — previously scattered across main.py and predict_service.py.
    """

    def __init__(self, orion_client: OrionClient) -> None:
        self._orion = orion_client
    
    # ── Publishers ───────────────────────────────────────────────────────────────

    async def publish_xgb_prediction(
        self,
        prediction_path: Path,
        input_entity_ids: list[str],
    ) -> str:
        """Register the XGBoost model prediction as UHIHeatMap."""
        entity = {
            "id": _XGB_HEATMAP_ENTITY_ID,
            "type": "UHIHeatMap",
            "name": {
                "type": "Property",
                "value": "UHI XGBoost Heat Map Brussels 2024",
            },
            "modelType": {"type": "Property", "value": "XGBoost"},
            "modelVersion": {"type": "Property", "value": "xgb_uhi_latest"},
            "dateGenerated": {
                "type": "Property",
                "value": datetime.now(timezone.utc).isoformat(),
            },
            "inputLayers": {"type": "Property", "value": input_entity_ids},
            "filePath": {"type": "Property", "value": str(prediction_path)},
            "geoserverLayer": {"type": "Property", "value": "uhi:uhi_xgb_heatmap"},
            "publishToGeoserver": {"type": "Property", "value": True},
            "valueRange": {
                "type": "Property",
                "value": {
                    "min": 0,
                    "max": 1,
                    "description": "UHI intensity (0=cool, 1=hot)",
                    "encoding": "uint8 [0–254] → [0–1], 255=nodata",
                },
            },
        }
        self._attach_bounding_box(entity, prediction_path)
        return await self._orion.upsert_entity(entity)

    async def publish_trained_model(
        self,
        model_path: Path,
        metrics: dict,
        config: dict,
        input_entity_ids: list[str],
    ) -> str:
        """Register a trained XGBoost model as a UHIModel entity."""
        entity = {
            "id": _MODEL_ENTITY_ID,
            "type": "UHIModel",
            "name": {
                "type": "Property",
                "value": "UHI XGBoost Model Brussels 2024",
            },
            "modelType": {"type": "Property", "value": "XGBoost"},
            "modelPath": {"type": "Property", "value": str(model_path)},
            "trainedAt": {
                "type": "Property",
                "value": datetime.now(timezone.utc).isoformat(),
            },
            "inputLayers": {"type": "Property", "value": input_entity_ids},
            "hyperparameters": {
                "type": "Property",
                "value": {
                    "n_estimators": config.get("n_estimators"),
                    "max_depth": config.get("max_depth"),
                    "learning_rate": config.get("learning_rate"),
                    "use_gpu": config.get("use_gpu"),
                    "sample_rate": config.get("sample_rate"),
                },
            },
            "metrics": {"type": "Property", "value": metrics},
        }
        return await self._orion.upsert_entity(entity)

    # — Helpers ——————————————————————————————————————————————————————————————

    @staticmethod
    def _attach_bounding_box(entity: dict, raster_path: Path) -> None:
        """
        Add a WGS-84 bounding box GeoProperty to the entity dict in-place.
        Silently skips if the raster cannot be opened.
        """
        try:
            with rasterio.open(raster_path) as src:
                left, bottom, right, top = transform_bounds(
                    src.crs, "EPSG:4326", *src.bounds
                )
            entity["boundingBox"] = {
                "type": "GeoProperty",
                "value": {
                    "type": "Polygon",
                    "coordinates": [[
                        [left, bottom], [right, bottom],
                        [right, top], [left, top], [left, bottom],
                    ]],
                },
            }
        except Exception as exc:
            logger.warning(f"Could not extract bounding box from '{raster_path}': {exc}")