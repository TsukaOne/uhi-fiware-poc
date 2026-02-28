"""
Application entry point — composition root only.

This file's single responsibility is wiring:
  config → infrastructure → domain → application → API

No business logic. No HTTP request handling. No os.getenv calls.
If you need to understand what the service does, read the orchestrators.
If you need to understand how it starts, read this file.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from algorithm.api.prediction_routeur import router as prediction_router
from algorithm.api.training_router import router as training_router
from algorithm.application.prediction_orchestrator import PredictionOrchestrator
from algorithm.application.training_orchestrator import TrainingOrchestrator
from algorithm.config import settings
from algorithm.domain.uhi_raster_engine import UHIRasterEngine
from algorithm.infrastructure.layer_resolver import LayerResolver
from algorithm.infrastructure.orion_client import OrionClient
from algorithm.infrastructure.orion_publisher import OrionPublisher
from algorithm.predict_service import _PredictionState
from algorithm.training_service import TrainingState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Build the dependency graph (all singletons) ───────────────────────────────
#
# Reading order = dependency order.
# Each line depends only on what is declared above it.

orion_client = OrionClient(settings)
layer_resolver = LayerResolver(orion_client)
orion_publisher = OrionPublisher(orion_client)
raster_engine = UHIRasterEngine()

training_state = TrainingState()
xgb_prediction_state = _PredictionState()

training_orchestrator = TrainingOrchestrator(
    settings=settings,
    publisher=orion_publisher,
    training_state=training_state,
)

prediction_orchestrator = PredictionOrchestrator(
    settings=settings,
    layer_resolver=layer_resolver,
    raster_engine=raster_engine,
    publisher=orion_publisher,
    xgb_prediction_state=xgb_prediction_state,
)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup sequence:
      1. Ensure output directory exists
      2. Register Orion subscription 
    """
    logger.info("Starting UHI Prediction Service")
    logger.info(f"  Orion URL    : {settings.orion_url}")
    logger.info(f"  Output path  : {settings.output_path}")
    logger.info(f"  NDVI entity  : {settings.ndvi_entity_id}")
    logger.info(f"  NDWI entity  : {settings.ndwi_entity_id}")

    settings.output_path.mkdir(parents=True, exist_ok=True)

    subscription = {
        "id": settings.prediction_subscription_id,
        "type": "Subscription",
        "description": "Trigger UHI prediction when NDVI or NDWI layers change",
        "entities": [
            {"id": settings.ndvi_entity_id, "type": "GeoSpatialLayer"},
            {"id": settings.ndwi_entity_id, "type": "GeoSpatialLayer"},
            {"id": settings.dtm_entity_id, "type": "GeoSpatialLayer"},
            {"id": settings.building_height_entity_id, "type": "GeoSpatialLayer"},
            {"id": settings.lst_entity_id, "type": "GeoSpatialLayer"},
        ],
        "watchedAttributes": ["filePath"],
        "notification": {
            "endpoint": {
                "uri": f"{settings.self_url}/predict",
                "accept": "application/json",
            }
        },
    }

    for attempt in range(5):
        try:
            await orion_client.upsert_subscription(subscription)
            break
        except Exception as exc:
            logger.warning(f"Subscription registration attempt {attempt + 1}/5 failed: {exc}")
            await asyncio.sleep(3)

    yield
    logger.info("Shutting down UHI Prediction Service")


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="UHI Prediction Service",
    description="Urban Heat Island prediction. Input paths resolved from Orion-LD at runtime.",
    version="3.0.0",
    lifespan=lifespan,
)

app.include_router(prediction_router)
app.include_router(training_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "prediction"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

## 5. Explication Pédagogique
