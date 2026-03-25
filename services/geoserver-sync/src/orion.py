"""
Orion-LD helpers.

  - derive_layer_info     : extract from an NGSI-LD entity the info needed to publish a layer in GeoServer.
  - sync_entity           : publish one entity to GeoServer (if applicable).
  - initial_sync          : sync all existing Orion entities on startup.
  - register_subscription : register (or recreate) the Orion-LD subscription.
"""
import logging
from typing import Optional

import httpx

from src.config import (
    ORION_URL,
    SELF_URL,
    NGSI_LD_CONTEXT,
    SUBSCRIPTION_ID,
    GEOSERVER_WORKSPACE,
    translate_path,
)
from src.geoserver import GeoServerClient
from src.styles import STYLES, STYLE_MAP

# Logger for this module
logger = logging.getLogger(__name__)

# Orion-LD entity types that this service watches
WATCHED_ENTITY_TYPES = ("GeoSpatialLayer", "UHIHeatMap")


# ---------------------------------------------------------------------------
# Layer info derivation from an NGSI-LD entity
# ---------------------------------------------------------------------------

def derive_layer_info(entity: dict) -> Optional[dict]:
    """Extract GeoServer publication info from an NGSI-LD entity.

    Returns None if the entity should not be published
    """
    # Only publish if publishToGeoserver is true
    if not entity.get("publishToGeoserver", {}).get("value", False):
        return None

    # Only publish if filePath is set
    file_path = entity.get("filePath", {}).get("value")
    if not file_path:
        logger.warning(
            "Entity %s has publishToGeoserver=true but no filePath — skipping",
            entity.get("id"),
        )
        return None

    entity_type = entity.get("type")

    if entity_type == "GeoSpatialLayer":
        name  = entity.get("layerType", {}).get("value", "unknown").lower()
        title = entity.get("name", {}).get("value", name)
        style = STYLE_MAP.get(name)

    elif entity_type == "UHIHeatMap":
        name  = "uhi_prediction"
        title = entity.get("name", {}).get("value", "UHI Heat Risk Prediction")
        style = STYLE_MAP.get(name)

    else:
        # Generic fallback: derive from the geoserverLayer property
        gs_layer = entity.get("geoserverLayer", {}).get("value", "")
        name  = gs_layer.split(":", 1)[1] if ":" in gs_layer else (
            gs_layer or entity.get("id", "unknown").split(":")[-1]
        )
        title = entity.get("name", {}).get("value", name)
        style = None

    return {
        "name":           name,
        "store_name":     f"store_{name}",
        "title":          title,
        "geoserver_path": translate_path(file_path),
        "style_name":     style,
    }


# ---------------------------------------------------------------------------
# Single entity sync
# ---------------------------------------------------------------------------

def sync_entity(entity: dict, geoserver: GeoServerClient) -> bool:
    """Publish one entity to GeoServer if applicable.

    Returns True if the layer was published, False otherwise.
    """
    info = derive_layer_info(entity)
    if info is None:
        return False

    logger.info(
        "Syncing entity %s → %s:%s  (file: %s)",
        entity.get("id"), GEOSERVER_WORKSPACE, info["name"], info["geoserver_path"],
    )

    if info["style_name"] and info["name"] in STYLES:
        geoserver.ensure_style(info["style_name"], STYLES[info["name"]])

    return geoserver.publish_layer(
        store_name=info["store_name"],
        coverage_name=info["name"],
        title=info["title"],
        file_path=info["geoserver_path"],
        style_name=info["style_name"],
    )


# ---------------------------------------------------------------------------
# Initial sync (all existing entities)
# ---------------------------------------------------------------------------

async def initial_sync(geoserver: GeoServerClient) -> None:
    """Query Orion for all existing entities and sync those with publishToGeoserver=true."""
    logger.info("Running initial sync of existing entities …")
    synced = 0

    for entity_type in WATCHED_ENTITY_TYPES:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    f"{ORION_URL}/ngsi-ld/v1/entities",
                    params={"type": entity_type, "local": "true"},
                    headers={"Accept": "application/json"},
                )
            if r.status_code != 200:
                logger.warning("Could not query %s: %s", entity_type, r.status_code)
                continue
            for entity in r.json():
                if sync_entity(entity, geoserver):
                    synced += 1
        except Exception as exc:
            logger.warning("Initial sync for %s failed: %s", entity_type, exc)

    logger.info("Initial sync complete — %d layer(s) published", synced)


# ---------------------------------------------------------------------------
# Orion-LD subscription
# ---------------------------------------------------------------------------

async def register_subscription() -> None:
    """Register (or recreate) the Orion-LD subscription pointing to this service."""
    subscription = {
        "@context":    NGSI_LD_CONTEXT,
        "id":          SUBSCRIPTION_ID,
        "type":        "Subscription",
        "description": "Sync publishable layers to GeoServer",
        "entities":    [{"type": t} for t in WATCHED_ENTITY_TYPES],
        "watchedAttributes": ["publishToGeoserver", "filePath"],
        "notification": {
            "endpoint": {
                "uri":    f"{SELF_URL}/sync",
                "accept": "application/json",
            }
        },
    }
    headers = {
        "Content-Type": "application/ld+json",
        "Accept":       "application/ld+json",
    }
    sub_url = f"{ORION_URL}/ngsi-ld/v1/subscriptions"

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(sub_url, json=subscription, headers=headers)

        if r.status_code == 201:
            logger.info("Subscription %s created", SUBSCRIPTION_ID)
            return

        if r.status_code == 409:
            # Already exists — delete and recreate to update endpoint / watched attrs
            await client.delete(f"{sub_url}/{SUBSCRIPTION_ID}")
            r = await client.post(sub_url, json=subscription, headers=headers)
            if r.status_code == 201:
                logger.info("Subscription %s recreated", SUBSCRIPTION_ID)
                return

        logger.error(
            "Failed to register subscription: %s %s",
            r.status_code, r.text,
        )
