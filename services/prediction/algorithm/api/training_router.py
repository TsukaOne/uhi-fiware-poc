"""
Training API Router — HTTP layer for training endpoints.

Single responsibility: HTTP concerns only.
All business logic is in TrainingOrchestrator and TrainingState.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException

from algorithm.application.training_orchestrator import TrainingOrchestrator
from algorithm.infrastructure.layer_resolver import LayerResolver
from algorithm.training_service import (
    TrainingConfig,
    TrainingResponse,
    TrainingState,
    TrainingStatusResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Endpoints ─────────────────────────────────────────────────────────────────

# ── Dependencies ──────────────────────────────────────────────────────────────

def _get_training_orchestrator() -> TrainingOrchestrator:
    from main import training_orchestrator
    return training_orchestrator


def _get_layer_resolver() -> LayerResolver:
    from main import layer_resolver
    return layer_resolver


def _get_training_state() -> TrainingState:
    from main import training_state
    return training_state


@router.post(
    "/training/start",
    response_model=TrainingResponse,
    summary="Start a training job",
)
async def start_training(
    config: TrainingConfig = TrainingConfig(),
    orchestrator: TrainingOrchestrator = Depends(_get_training_orchestrator),
    resolver: LayerResolver = Depends(_get_layer_resolver),
    state: TrainingState = Depends(_get_training_state),
):
    """
    Launch an XGBoost training job in the background.

    Input layer paths are resolved from Orion at request time — fails fast
    if Orion is down or a required entity is missing.
    Poll /training/status for progress.
    """
    if state.is_running:
        raise HTTPException(409, "A training job is already running. Poll /training/status.")

    # Resolve eagerly — fail here with a clean HTTP error, not inside the thread
    from algorithm.config import settings
    paths = await resolver.resolve_required(settings.all_layer_entity_ids)

    cfg = config.model_dump()
    state.start(cfg)

    loop = asyncio.get_running_loop()
    thread = orchestrator.launch(paths=paths, config=cfg, event_loop=loop)

    return TrainingResponse(
        status="accepted",
        message="Training started in background. Poll /training/status.",
        job_id=thread.name,
    )


@router.get(
    "/training/status",
    response_model=TrainingStatusResponse,
    summary="Get training job status",
)
async def get_training_status(
    state: TrainingState = Depends(_get_training_state),
):
    """Return the current state of the training job."""
    return state.snapshot()


@router.delete(
    "/training/cache",
    summary="Clear training sample cache",
)
async def clear_training_cache(
    state: TrainingState = Depends(_get_training_state),
):
    """
    Delete the cached training samples.
    Forces the next training run to resample from scratch.
    """
    if state.is_running:
        raise HTTPException(409, "Cannot clear cache while training is running.")

    from algorithm.config import settings
    cache_file = settings.cache_path / "training_samples.npz"

    if cache_file.exists():
        cache_file.unlink()
        return {"status": "cleared", "path": str(cache_file)}

    return {"status": "nothing_to_clear", "path": str(cache_file)}

