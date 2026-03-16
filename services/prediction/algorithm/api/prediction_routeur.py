"""
Prediction API Router — HTTP layer for prediction endpoints.

Single responsibility: parse HTTP requests, call the orchestrator,
return HTTP responses. No business logic here.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from algorithm.application.prediction_orchestrator import PredictionOrchestrator
from algorithm.predict_service import MapResponse, MapStatusResponse

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request / Response schemas ────────────────────────────────────────────────

class NotificationPayload(BaseModel):
    """Orion-LD notification envelope (wraps one or more changed entities)."""
    id: str
    type: str
    subscriptionId: Optional[str] = None
    notifiedAt: Optional[str] = None
    data: list[dict] = []


class PredictionResponse(BaseModel):
    status: str
    message: str
    prediction_path: Optional[str] = None
    entity_id: Optional[str] = None
    input_layers: Optional[dict[str, str]] = None

# ── Dependency ────────────────────────────────────────

def _get_orchestrator() -> PredictionOrchestrator:
    """
    FastAPI dependency — returns the app-scoped PredictionOrchestrator.

    """
    from main import prediction_orchestrator
    return prediction_orchestrator

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/predict/map", response_model=MapResponse)
async def launch_xgb_prediction(
    orchestrator: PredictionOrchestrator = Depends(_get_orchestrator),
):
    """
    Launch the XGBoost tiled inference pipeline in a background thread.
    Poll GET /predict/map/status to follow progress.
    """
    if orchestrator.xgb_prediction_is_running:
        raise HTTPException(409, "A prediction job is already running.")

    loop = asyncio.get_running_loop()
    await orchestrator.launch_xgb_prediction(loop)

    return MapResponse(
        status="accepted",
        message="XGBoost prediction started. Poll /predict/map/status.",
    )


@router.get("/predict/map/status", response_model=MapStatusResponse)
async def xgb_prediction_status(
    orchestrator: PredictionOrchestrator = Depends(_get_orchestrator),
):
    """Return current status of the XGBoost prediction job."""
    return MapStatusResponse(**orchestrator.xgb_prediction_state.snapshot())