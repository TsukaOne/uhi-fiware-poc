"""
Prediction Orchestrator — coordinates both prediction pipelines.

Manages:
  1. Legacy NDVI-based prediction  (asyncio.Lock deduplication)
  2. XGBoost tiled inference       (background thread + PredictionState)

"""
from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path

from algorithm.config import Settings
from algorithm.domain.uhi_raster_engine import UHIRasterEngine
from algorithm.infrastructure.layer_resolver import LayerResolver
from algorithm.infrastructure.orion_publisher import OrionPublisher
from algorithm.predict_service import _PredictionState, _prediction_job

logger = logging.getLogger(__name__)


class PredictionOrchestrator:
    """
    Coordinates UHI prediction jobs.
    """

    def __init__(
        self,
        settings: Settings,
        layer_resolver: LayerResolver,
        raster_engine: UHIRasterEngine,
        publisher: OrionPublisher,
        xgb_prediction_state: _PredictionState,
    ) -> None:
        self._settings = settings 
        self._resolver = layer_resolver
        self._engine = raster_engine
        self._publisher = publisher
        self._xgb_state = xgb_prediction_state
        # Lock prevents duplicate concurrent legacy predictions
        self._legacy_lock = asyncio.Lock()

    # ── Use case 1: Legacy NDVI prediction ───────────────────────────

    @property
    def legacy_prediction_is_running(self) -> bool:
        return self._legacy_lock.locked()

    async def run_legacy_prediction(self) -> dict:
        """
        Run the NDVI→heat-risk prediction pipeline.

        Guarded by an asyncio.Lock — concurrent calls are deduplicated.
        Returns a dict suitable for PredictionResponse.
        """
        async with self._legacy_lock:
            layers = await self._resolver.resolve_with_optional(
                required={"ndvi": self._settings.ndvi_entity_id},
                optional={"ndwi": self._settings.ndwi_entity_id},
            )

            output_path = (
                self._settings.output_path / "uhi_prediction_brussels_2024.tif"
            )
            # Raster engine is synchronous and CPU/IO-bound → run in thread
            prediction_path = await asyncio.to_thread(
                self._engine.generate,
                layers["ndvi"],
                output_path,
            )

            input_ids = [self._settings.ndvi_entity_id] + (
                [self._settings.ndwi_entity_id] if "ndwi" in layers else []
            )
            entity_id = await self._publisher.publish_legacy_prediction(
                prediction_path, input_ids
            )

            return {
                "status": "success",
                "message": "UHI prediction generated (placeholder: NDVI-based)",
                "prediction_path": str(prediction_path),
                "entity_id": entity_id,
                "input_layers": {k: str(v) for k, v in layers.items()},
            }

    # ── Use case 2: XGBoost tiled inference ──────────────────────────

    @property
    def xgb_prediction_is_running(self) -> bool:
        return self._xgb_state.is_running

    async def launch_xgb_prediction(
        self,
        event_loop: asyncio.AbstractEventLoop,
    ) -> None:
        """
        Resolve input layers eagerly, then start inference in a background thread.

        Resolving paths before launching the thread ensures fast failure:
        if Orion is down, we return a 503 immediately instead of discovering
        it inside a thread with no HTTP response channel.
        """
        paths = await self._resolver.resolve_required(
            self._settings.all_layer_entity_ids
        )

        self._xgb_state.start()

        thread = threading.Thread(
            target=_prediction_job,
            kwargs=dict(paths=paths, loop=event_loop),
            daemon=True,
            name="uhi-xgb-prediction-job",
        )
        thread.start()
        logger.info(f"XGBoost prediction thread started: {thread.name}")