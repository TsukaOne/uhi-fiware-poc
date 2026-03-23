"""
GeoServer Sync Service

Listens to Orion-LD notifications for GeoSpatialLayer and UHIHeatMap entities.
When an entity has ``publishToGeoserver=true``, this service ensures the corresponding
layer is published in GeoServer.

Architecture:
  - Startup      : wait for GeoServer → ensure workspace → initial sync → register subscription
  - Notification : publish / update the layer in GeoServer
  - No hardcoded paths or layer names — everything is derived from Orion entities.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from src.config import (
    GEOSERVER_URL,
    GEOSERVER_USER,
    GEOSERVER_PASSWORD,
    GEOSERVER_WORKSPACE,
    ORION_URL,
    PATH_MAPPINGS,
)

from src.geoserver import GeoServerClient
from src.orion import initial_sync, register_subscription, sync_entity

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# Configure logging at the module level to ensure it's set up before any log messages are emitted
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GeoServer singleton
# ---------------------------------------------------------------------------
geoserver = GeoServerClient(
    base_url=GEOSERVER_URL,
    user=GEOSERVER_USER,
    password=GEOSERVER_PASSWORD,
    workspace=GEOSERVER_WORKSPACE,
)


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting GeoServer Sync Service")
    logger.info("  Orion URL      : %s", ORION_URL)
    logger.info("  GeoServer URL  : %s", GEOSERVER_URL)
    logger.info("  Workspace      : %s", GEOSERVER_WORKSPACE)
    logger.info("  Path mappings  : %s", PATH_MAPPINGS)

    # Wait for GeoServer to be ready before sync and subscription
    await asyncio.to_thread(geoserver.wait_until_ready)
    # Ensure the workspace exists
    await asyncio.to_thread(geoserver.ensure_workspace)

    # Initial sync + subscription 
    for attempt in range(10):
        try:
            await initial_sync(geoserver)
            await register_subscription()
            break
        except Exception as exc:
            logger.warning("Attempt %d/10 failed: %s", attempt + 1, exc)
            await asyncio.sleep(5)

    yield
    logger.info("Shutting down GeoServer Sync Service")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="GeoServer Sync Service",
    description=(
        "Keeps GeoServer in sync with Orion-LD entities. "
        "Layers with publishToGeoserver=true are automatically published."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class NotificationPayload(BaseModel):
    """Orion-LD notification payload."""
    id:             str
    type:           str
    subscriptionId: Optional[str] = None
    notifiedAt:     Optional[str] = None
    data:           list[dict]    = []


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "geoserver-sync"}


@app.post("/sync")
async def handle_notification(notification: NotificationPayload):
    """Receive an Orion-LD notification and sync the affected entities to GeoServer."""
    logger.info(
        "Notification %s received — %d entity/entities",
        notification.id, len(notification.data),
    )
    results = []
    for entity in notification.data:
        entity_id = entity.get("id", "?")
        ok = await asyncio.to_thread(sync_entity, entity, geoserver)
        results.append({"entity": entity_id, "synced": ok})
        if ok:
            logger.info("  ✓ Synced %s", entity_id)
        else:
            logger.info("  – Skipped %s (publishToGeoserver != true or filePath missing)", entity_id)

    return {"status": "ok", "results": results}


@app.post("/sync/all")
async def force_sync_all():
    """Force a full re-sync of all Orion entities to GeoServer."""
    await initial_sync(geoserver)
    return {"status": "ok", "message": "Full re-sync completed"}


# ---------------------------------------------------------------------------
# Entry point (local development)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
