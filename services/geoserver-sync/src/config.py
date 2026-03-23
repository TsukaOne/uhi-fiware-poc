"""
Configuration — environment variables and path mapping.
"""
import os
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Service endpoints
# ---------------------------------------------------------------------------
ORION_URL           = os.getenv("ORION_URL",           "http://orion:1026")
GEOSERVER_URL       = os.getenv("GEOSERVER_URL",       "http://geoserver:8080/geoserver")
GEOSERVER_USER      = os.getenv("GEOSERVER_USER",      "admin")
GEOSERVER_PASSWORD  = os.getenv("GEOSERVER_PASSWORD",  "geoserver")
GEOSERVER_WORKSPACE = os.getenv("GEOSERVER_WORKSPACE", "uhi")

# URL Orion uses to reach this service (Docker-internal network)
SELF_URL = os.getenv("SELF_URL", "http://geoserver-sync:8000")

# ---------------------------------------------------------------------------
# NGSI-LD
# ---------------------------------------------------------------------------
NGSI_LD_CONTEXT = "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"
SUBSCRIPTION_ID = "urn:ngsi-ld:Subscription:geoserver-sync"

# ---------------------------------------------------------------------------
# Path mapping
#
# Ingestion containers write files under /data/processed/ or /data/raw/.
# GeoServer sees the same host directories mounted at different internal paths.
#
# Environment variable format:
#   PATH_MAP_<label>=<source_prefix>:<geoserver_prefix>
#
# Example:
#   PATH_MAP_PROCESSED=/data/processed:/opt/geoserver_data/data/uhi_processed
# ---------------------------------------------------------------------------

def _load_path_mappings() -> dict[str, str]:
    """Build the path mapping dict from PATH_MAP_* environment variables."""
    mappings: dict[str, str] = {}
    for key, value in os.environ.items():
        if key.startswith("PATH_MAP_"):
            parts = value.split(":", 1)
            if len(parts) == 2:
                mappings[parts[0]] = parts[1]

    if mappings:
        return mappings

    # Fallback defaults when no environment variable is defined
    return {
        "/data/processed": "/opt/geoserver_data/data/uhi_processed",
        "/data/raw":       "/opt/geoserver_data/data/uhi_raw",
    }


PATH_MAPPINGS: dict[str, str] = _load_path_mappings()


def translate_path(container_path: str) -> str:
    """Translate a container file path to GeoServer's internal path.

    Longer mappings take precedence (sorted by descending length).
    """
    for src, dst in sorted(PATH_MAPPINGS.items(), key=lambda kv: -len(kv[0])):
        if container_path.startswith(src):
            return container_path.replace(src, dst, 1)
    logger.warning("No path mapping found for %r — using path as-is", container_path)
    return container_path
