"""
GeoServer Sync Service

Listens to Orion-LD notifications for GeoSpatialLayer and UHIHeatMap
entities.  When an entity has ``publishToGeoserver=true``, this service
ensures the corresponding layer is published in GeoServer.

Architecture:
  - On startup  : wait for GeoServer → ensure workspace → initial sync → register subscription
  - On notification : publish / update layer in GeoServer
  - No hardcoded file paths or layer names – everything is derived from Orion entities.
"""

import os
import asyncio
import logging
import time
from typing import Optional
from contextlib import asynccontextmanager
from xml.sax.saxutils import escape as xml_escape

from fastapi import FastAPI
from pydantic import BaseModel
import httpx

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ORION_URL = os.getenv("ORION_URL", "http://orion:1026")
GEOSERVER_URL = os.getenv("GEOSERVER_URL", "http://geoserver:8080/geoserver")
GEOSERVER_USER = os.getenv("GEOSERVER_USER", "admin")
GEOSERVER_PASSWORD = os.getenv("GEOSERVER_PASSWORD", "geoserver")
GEOSERVER_WORKSPACE = os.getenv("GEOSERVER_WORKSPACE", "uhi")

# URL that Orion uses to reach this service (Docker-internal)
SELF_URL = os.getenv("SELF_URL", "http://geoserver-sync:8000")

NGSI_LD_CONTEXT = "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"
SUBSCRIPTION_ID = "urn:ngsi-ld:Subscription:geoserver-sync"

# ---------------------------------------------------------------------------
# Path mapping
#
# Files stored by the ingestion / prediction containers live under paths
# like /data/processed/… or /data/raw/….  GeoServer sees the *same* host
# directories mounted at different internal paths.
#
# Env-var format:  PATH_MAP_<label>=<source_prefix>:<geoserver_prefix>
# Example:         PATH_MAP_PROCESSED=/data/processed:/opt/geoserver_data/data/uhi_processed
# ---------------------------------------------------------------------------
PATH_MAPPINGS: dict[str, str] = {}

for _key, _value in os.environ.items():
    if _key.startswith("PATH_MAP_"):
        parts = _value.split(":", 1)
        if len(parts) == 2:
            PATH_MAPPINGS[parts[0]] = parts[1]

if not PATH_MAPPINGS:
    PATH_MAPPINGS = {
        "/data/processed": "/opt/geoserver_data/data/uhi_processed",
        "/data/raw": "/opt/geoserver_data/data/uhi_raw",
    }


def translate_path(container_path: str) -> str:
    """Translate a container file path to GeoServer's internal path."""
    for src, dst in sorted(PATH_MAPPINGS.items(), key=lambda x: -len(x[0])):
        if container_path.startswith(src):
            return container_path.replace(src, dst, 1)
    logger.warning(f"No path mapping found for {container_path}, using as-is")
    return container_path

# ===================================================================
# Style definitions
# ===================================================================

STYLES = {
    "dtm": """<?xml version="1.0" encoding="UTF-8"?>
    <StyledLayerDescriptor version="1.0.0" 
        xmlns="http://www.opengis.net/sld" 
        xmlns:ogc="http://www.opengis.net/ogc"
        xmlns:xlink="http://www.w3.org/1999/xlink">
        <NamedLayer>
            <Name>dtm</Name>
            <UserStyle>
            <Name>dtm_style</Name>
            <Title>Digital Terrain Model - Brussels</Title>
            <FeatureTypeStyle>
                <Rule>
                <RasterSymbolizer>
                    
                    <ColorMap type="ramp">
                        <!-- 0 = NoData transparent -->
                        <ColorMapEntry color="#000000" quantity="0" opacity="0" label="NoData"/>
                        
                        <!-- Palier très fin pour plus de contraste -->
                        <ColorMapEntry color="#1a1a1a" quantity="1" opacity="1"/>
                        <ColorMapEntry color="#2b2b2b" quantity="10" opacity="1"/>
                        <ColorMapEntry color="#3c3c3c" quantity="20" opacity="1"/>
                        <ColorMapEntry color="#4d4d4d" quantity="30" opacity="1"/>
                        <ColorMapEntry color="#5e5e5e" quantity="50" opacity="1"/>
                        <ColorMapEntry color="#6f6f6f" quantity="70" opacity="1"/>
                        <ColorMapEntry color="#808080" quantity="90" opacity="1"/>
                        <ColorMapEntry color="#919191" quantity="110" opacity="1"/>
                        <ColorMapEntry color="#a2a2a2" quantity="130" opacity="1"/>
                        <ColorMapEntry color="#b3b3b3" quantity="150" opacity="1"/>
                        <ColorMapEntry color="#c4c4c4" quantity="170" opacity="1"/>
                        <ColorMapEntry color="#d5d5d5" quantity="190" opacity="1"/>
                        <ColorMapEntry color="#e6e6e6" quantity="220" opacity="1"/>
                        <ColorMapEntry color="#ffffff" quantity="254" opacity="1"/>
                    </ColorMap>
                </RasterSymbolizer>
                </Rule>
            </FeatureTypeStyle>
            </UserStyle>
        </NamedLayer>
    </StyledLayerDescriptor>""",

    "ndwi": """<?xml version="1.0" encoding="UTF-8"?>
    <StyledLayerDescriptor version="1.0.0" 
        xmlns="http://www.opengis.net/sld" 
        xmlns:ogc="http://www.opengis.net/ogc"
        xmlns:xlink="http://www.w3.org/1999/xlink">
        <NamedLayer>
            <Name>ndwi</Name>
            <UserStyle>
            <Name>ndwi_style</Name>
            <Title>Normalized Difference Water Index - Brussels</Title>
            <FeatureTypeStyle>
                <Rule>
                <RasterSymbolizer>
                    <ColorMap>
                        <ColorMapEntry color="#8c510a" quantity="0" opacity="1"/>
                        <ColorMapEntry color="#bf812d" quantity="33" opacity="1"/>
                        <ColorMapEntry color="#dfc27d" quantity="66" opacity="1"/>
                        <ColorMapEntry color="#f6e8c3" quantity="90" opacity="1"/>
                        <ColorMapEntry color="#ffffff" quantity="127" opacity="1"/>
                        <ColorMapEntry color="#c7eae5" quantity="150" opacity="1"/>
                        <ColorMapEntry color="#80cdc1" quantity="170" opacity="1"/>
                        <ColorMapEntry color="#35978f" quantity="191" opacity="1"/>
                        <ColorMapEntry color="#01665e" quantity="220" opacity="1"/>
                        <ColorMapEntry color="#003c30" quantity="254" opacity="1"/>
                    </ColorMap>
                </RasterSymbolizer>
                </Rule>
            </FeatureTypeStyle>
            </UserStyle>
        </NamedLayer>
    </StyledLayerDescriptor>""",

    "ndvi": """<?xml version="1.0" encoding="UTF-8"?>
    <StyledLayerDescriptor version="1.0.0" 
        xmlns="http://www.opengis.net/sld" 
        xmlns:ogc="http://www.opengis.net/ogc"
        xmlns:xlink="http://www.w3.org/1999/xlink">
        <NamedLayer>
            <Name>ndvi</Name>
            <UserStyle>
            <Name>ndvi_style</Name>
            <Title>Normalized Difference Vegetation Index - Brussels</Title>
            <FeatureTypeStyle>
                <Rule>
                <RasterSymbolizer>
                    <ColorMap>
                            <ColorMapEntry color="#d7191c" quantity="0" opacity="1" label="No vegetation"/>
                            <ColorMapEntry color="#d53b22" quantity="33" opacity="1"/>
                            <ColorMapEntry color="#d35d28" quantity="66" opacity="1"/>
                            <ColorMapEntry color="#d17f2e" quantity="99" opacity="1"/>
                            <ColorMapEntry color="#ebc781" quantity="132" opacity="1"/>
                            <ColorMapEntry color="#d2f79f" quantity="165" opacity="1"/>
                            <ColorMapEntry color="#3ed537" quantity="198" opacity="1"/>
                            <ColorMapEntry color="#2ab33d" quantity="229" opacity="1"/>
                            <ColorMapEntry color="#1a9641" quantity="254" opacity="1" label="High vegetation"/>                    
                    </ColorMap>
                </RasterSymbolizer>
                </Rule>
            </FeatureTypeStyle>
            </UserStyle>
        </NamedLayer>
    </StyledLayerDescriptor>""",

    "rgb": """<?xml version="1.0" encoding="UTF-8"?>
    <StyledLayerDescriptor version="1.0.0" 
        xmlns="http://www.opengis.net/sld" 
        xmlns:ogc="http://www.opengis.net/ogc"
        xmlns:xlink="http://www.w3.org/1999/xlink">
        <NamedLayer>
            <Name>rgb</Name>
            <UserStyle>
            <Name>rgb_style</Name>
            <Title>Red Green Blue - Brussels</Title>
            <FeatureTypeStyle>
                <Rule>
               <RasterSymbolizer>

                <ChannelSelection>
                    <RedChannel>
                    <SourceChannelName>1</SourceChannelName>
                    </RedChannel>
                    <GreenChannel>
                    <SourceChannelName>2</SourceChannelName>
                    </GreenChannel>
                    <BlueChannel>
                    <SourceChannelName>3</SourceChannelName>
                    </BlueChannel>
                </ChannelSelection>

                </RasterSymbolizer>
                </Rule>
            </FeatureTypeStyle>
            </UserStyle>
        </NamedLayer>
    </StyledLayerDescriptor>""",

    "nir": """<?xml version="1.0" encoding="UTF-8"?>
    <StyledLayerDescriptor version="1.0.0" 
        xmlns="http://www.opengis.net/sld" 
        xmlns:ogc="http://www.opengis.net/ogc"
        xmlns:xlink="http://www.w3.org/1999/xlink">
        <NamedLayer>
            <Name>nir</Name>
            <UserStyle>
            <Name>nir_style</Name>
            <Title>Near Infrared - Brussels</Title>
            <FeatureTypeStyle>
                <Rule>
                <RasterSymbolizer>
                    <ChannelSelection>
                        <RedChannel>
                        <SourceChannelName>1</SourceChannelName>
                        </RedChannel>
                        <GreenChannel>
                        <SourceChannelName>2</SourceChannelName>
                        </GreenChannel>
                        <BlueChannel>
                        <SourceChannelName>3</SourceChannelName>
                        </BlueChannel>
                    </ChannelSelection>

                    </RasterSymbolizer>
                </Rule>
            </FeatureTypeStyle>
            </UserStyle>
        </NamedLayer>
    </StyledLayerDescriptor>""",
    
    "uhi_prediction": """<?xml version="1.0" encoding="UTF-8"?>
    <StyledLayerDescriptor version="1.0.0"
        xmlns="http://www.opengis.net/sld"
        xmlns:ogc="http://www.opengis.net/ogc"
        xmlns:xlink="http://www.w3.org/1999/xlink">
        <NamedLayer>
            <Name>uhi_prediction</Name>
            <UserStyle>
                <Name>uhi_prediction_style</Name>
                <Title>Urban Heat Island Prediction (RdYlBu)</Title>
                <FeatureTypeStyle>
                    <Rule>
                        <RasterSymbolizer>
                            <ColorMap type="ramp">

                                <!-- Froid (Bleu) -->
                                <ColorMapEntry color="#313695" quantity="0" opacity="1" label="Very Cold"/>
                                <ColorMapEntry color="#4575b4" quantity="50" opacity="1"/>
                                <ColorMapEntry color="#74add1" quantity="90" opacity="1"/>

                                <!-- Transition -->
                                <ColorMapEntry color="#abd9e9" quantity="110" opacity="1"/>
                                <ColorMapEntry color="#ffffbf" quantity="127" opacity="1" label="Neutral"/>

                                <!-- Chaud -->
                                <ColorMapEntry color="#fdae61" quantity="160" opacity="1"/>
                                <ColorMapEntry color="#f46d43" quantity="190" opacity="1"/>
                                <ColorMapEntry color="#d73027" quantity="220" opacity="1"/>
                                <ColorMapEntry color="#a50026" quantity="254" opacity="1" label="Very Hot"/>

                            </ColorMap>
                        </RasterSymbolizer>
                    </Rule>
                </FeatureTypeStyle>
            </UserStyle>
        </NamedLayer>
    </StyledLayerDescriptor>""",
    "lst": """<?xml version="1.0" encoding="UTF-8"?>
    <StyledLayerDescriptor version="1.0.0"
        xmlns="http://www.opengis.net/sld"
        xmlns:ogc="http://www.opengis.net/ogc"
        xmlns:xlink="http://www.w3.org/1999/xlink">
        <NamedLayer>
            <Name>lst</Name>
            <UserStyle>
                <Name>lst_style</Name>
                <Title>Land Surface Temperature</Title>
                <FeatureTypeStyle>
                    <Rule>
                        <RasterSymbolizer>
                            <ColorMap type="ramp">

                                <!-- Froid (Bleu) -->
                                <ColorMapEntry color="#313695" quantity="0" opacity="1" label="Very Cold"/>
                                <ColorMapEntry color="#4575b4" quantity="50" opacity="1"/>
                                <ColorMapEntry color="#74add1" quantity="90" opacity="1"/>

                                <!-- Transition -->
                                <ColorMapEntry color="#abd9e9" quantity="110" opacity="1"/>
                                <ColorMapEntry color="#ffffbf" quantity="127" opacity="1" label="Neutral"/>

                                <!-- Chaud -->
                                <ColorMapEntry color="#fdae61" quantity="160" opacity="1"/>
                                <ColorMapEntry color="#f46d43" quantity="190" opacity="1"/>
                                <ColorMapEntry color="#d73027" quantity="220" opacity="1"/>
                                <ColorMapEntry color="#a50026" quantity="254" opacity="1" label="Very Hot"/>

                            </ColorMap>
                        </RasterSymbolizer>
                    </Rule>
                </FeatureTypeStyle>
            </UserStyle>
        </NamedLayer>
    </StyledLayerDescriptor>"""

}
# ===================================================================
# GeoServer REST client
# ===================================================================

class GeoServerClient:
    """Thin wrapper around the GeoServer REST API."""

    def __init__(
        self,
        base_url: str,
        user: str,
        password: str,
        workspace: str,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth = (user, password)
        self.workspace = workspace

    # -- helpers ----------------------------------------------------------

    def _client(self) -> httpx.Client:
        return httpx.Client(
            timeout=30.0,
            auth=self.auth,
            follow_redirects=True,
        )

    # -- readiness --------------------------------------------------------

    def wait_until_ready(self, timeout: int = 180) -> None:
        """Block until the GeoServer REST API responds."""
        logger.info(f"Waiting for GeoServer at {self.base_url} …")
        start = time.time()
        while time.time() - start < timeout:
            try:
                with self._client() as c:
                    r = c.get(f"{self.base_url}/rest/about/version.json")
                    if r.status_code == 200:
                        logger.info("GeoServer is ready")
                        return
            except Exception:
                pass
            time.sleep(3)
        raise RuntimeError(
            f"GeoServer at {self.base_url} did not become ready "
            f"within {timeout}s"
        )

    # -- workspace --------------------------------------------------------

    def ensure_workspace(self) -> None:
        """Create the workspace if it does not exist yet."""
        with self._client() as c:
            r = c.get(f"{self.base_url}/rest/workspaces/{self.workspace}")
            if r.status_code == 200:
                logger.info(f"Workspace '{self.workspace}' already exists")
                return

            xml = f"<workspace><name>{self.workspace}</name></workspace>"
            r = c.post(
                f"{self.base_url}/rest/workspaces",
                content=xml,
                headers={"Content-Type": "application/xml"},
            )
            if r.status_code == 201:
                logger.info(f"Created workspace '{self.workspace}'")
            else:
                logger.error(
                    f"Failed to create workspace: {r.status_code} {r.text}"
                )


    # -- styles -----------------------------------------------------------

    def ensure_style(self, style_name: str, sld_content: str) -> bool:
        ws = self.workspace
        style_url = f"{self.base_url}/rest/workspaces/{ws}/styles/{style_name}"

        with self._client() as c:
            r = c.get(style_url)

            # 500 = style corrompu côté GeoServer → supprimer et recréer
            if r.status_code == 500:
                logger.warning(
                    f"Style '{style_name}' returned 500 — deleting and recreating"
                )
                del_r =c.delete(style_url, params={"purge": "true", "recurse": "true"})
                if del_r.status_code not in (200, 404):
                    # Toujours refusé — tenter un PUT direct avec le SLD quand même
                    logger.warning(
                        f"Could not delete corrupt style '{style_name}' "
                        f"({del_r.status_code}) — attempting direct PUT"
                    )
                    r2 = c.put(
                        style_url,
                        content=sld_content.encode("utf-8"),
                        headers={"Content-Type": "application/vnd.ogc.sld+xml"},
                    )
                    if r2.status_code in (200, 201):
                        logger.info(f"Overwrote corrupt style '{ws}:{style_name}' via PUT")
                        return True
                    logger.error(f"Failed to overwrite style: {r2.status_code} {r2.text}")
                    return False

                r = type('R', (), {'status_code': 404})()  # forcer le chemin création

            exists = r.status_code == 200

            if exists:
                # Style sain → PUT direct du SLD
                r = c.put(
                    style_url,
                    content=sld_content.encode("utf-8"),
                    headers={"Content-Type": "application/vnd.ogc.sld+xml"},
                )
                if r.status_code in (200, 201):
                    logger.info(f"Updated style '{ws}:{style_name}'")
                    return True
                logger.error(
                    f"Failed to update style '{style_name}': "
                    f"{r.status_code} {r.text}"
                )
                return False

            # Style absent → création en deux étapes (obligatoire pour workspace-scoped)
            # Étape 1 : déclarer le nom du style
            descriptor_xml = (
                f"<style>"
                f"  <name>{style_name}</name>"
                f"  <filename>{style_name}.sld</filename>"
                f"</style>"
            )
            r = c.post(
                f"{self.base_url}/rest/workspaces/{ws}/styles",
                content=descriptor_xml.encode("utf-8"),
                headers={"Content-Type": "application/xml"},
            )
            if r.status_code not in (200, 201):
                logger.error(
                    f"Failed to declare style '{style_name}': "
                    f"{r.status_code} {r.text}"
                )
                return False

            # Étape 2 : pousser le contenu SLD
            r = c.put(
                style_url,
                content=sld_content.encode("utf-8"),
                headers={"Content-Type": "application/vnd.ogc.sld+xml"},
            )
            if r.status_code in (200, 201):
                logger.info(f"Created style '{ws}:{style_name}'")
                return True

            logger.error(
                f"Failed to upload SLD for '{style_name}': "
                f"{r.status_code} {r.text}"
            )
            return False


    # -- publish ----------------------------------------------------------

    def publish_layer(
        self,
        store_name: str,
        coverage_name: str,
        title: str,
        file_path: str,
        style_name: Optional[str] = None,
    ) -> bool:
        """
        Idempotently create a GeoTIFF coverage-store + coverage+ apply style.

        Returns True on success.
        """
        ws = self.workspace
        safe_title = xml_escape(title)

        with self._client() as c:
            # 1) Coverage store — create or update
            store_url = (
                f"{self.base_url}/rest/workspaces/{ws}"
                f"/coveragestores/{store_name}"
            )
            r = c.get(store_url)

            store_xml = (
                f"<coverageStore>"
                f"  <name>{store_name}</name>"
                f"  <workspace><name>{ws}</name></workspace>"
                f"  <enabled>true</enabled>"
                f"  <type>GeoTIFF</type>"
                f"  <url>file:{file_path}</url>"
                f"</coverageStore>"
            )

            if r.status_code != 200:
                # create
                r = c.post(
                    f"{self.base_url}/rest/workspaces/{ws}/coveragestores",
                    content=store_xml,
                    headers={"Content-Type": "application/xml"},
                )
                if r.status_code not in (200, 201):
                    logger.error(
                        f"Failed to create store '{store_name}': "
                        f"{r.status_code} {r.text}"
                    )
                    return False
                logger.info(f"Created coverage store '{store_name}'")
            else:
                # update (e.g. file path changed)
                r = c.put(
                    store_url,
                    content=store_xml,
                    headers={"Content-Type": "application/xml"},
                )
                if r.status_code in (200, 201):
                    logger.info(f"Updated coverage store '{store_name}'")

           # 2) Coverage — create if missing
            cov_url = (
                f"{self.base_url}/rest/workspaces/{ws}"
                f"/coveragestores/{store_name}/coverages/{coverage_name}"
            )
            r = c.get(cov_url)
            
            if r.status_code != 200:
                cov_xml = (
                    f"<coverage>"
                    f"  <name>{coverage_name}</name>"
                    f"  <title>{safe_title}</title>"
                    f"  <enabled>true</enabled>"
                    f"</coverage>"
                )
                r = c.post(
                    f"{self.base_url}/rest/workspaces/{ws}"
                    f"/coveragestores/{store_name}/coverages",
                    content=cov_xml,
                    headers={"Content-Type": "application/xml"},
                )
                if r.status_code != 201:
                    logger.error(
                        f"Failed to publish coverage '{coverage_name}': "
                        f"{r.status_code} {r.text}"
                    )
                    return False
                logger.info(f"Published coverage '{ws}:{coverage_name}'")
            else:
                logger.info(f"Coverage '{ws}:{coverage_name}' already exists")

            layer_url = f"{self.base_url}/rest/layers/{ws}:{coverage_name}"
            r = c.get(layer_url)

            # 3) Ensure Layer exists 
            layer_url = f"{self.base_url}/rest/layers/{ws}:{coverage_name}"
            r = c.get(layer_url)

            if r.status_code != 200:
                logger.warning(f"Layer '{ws}:{coverage_name}' missing — recreating via coverage")

                # Delete coverage
                del_cov_url = (
                    f"{self.base_url}/rest/workspaces/{ws}"
                    f"/coveragestores/{store_name}/coverages/{coverage_name}?recurse=true"
                )

                r = c.delete(del_cov_url)
                if r.status_code not in (200, 202):
                    logger.error(f"Failed to delete coverage: {r.status_code} {r.text}")
                    return False

                # Recreate coverage (this recreates layer automatically)
                cov_xml = (
                    f"<coverage>"
                    f"  <name>{coverage_name}</name>"
                    f"  <title>{safe_title}</title>"
                    f"  <enabled>true</enabled>"
                    f"</coverage>"
                )

                r = c.post(
                    f"{self.base_url}/rest/workspaces/{ws}"
                    f"/coveragestores/{store_name}/coverages",
                    content=cov_xml,
                    headers={"Content-Type": "application/xml"},
                )

                if r.status_code != 201:
                    logger.error(f"Failed to recreate coverage: {r.status_code} {r.text}")
                    return False

                logger.info(f"Recreated coverage + layer '{ws}:{coverage_name}'")
            else:
                if style_name:
                    layer_xml = (
                        f"<layer>"
                        f"  <defaultStyle><name>{style_name}</name><workspace>{ws}</workspace></defaultStyle>"
                        f"</layer>"
                    )
                    r = c.put(
                        layer_url,
                        content=layer_xml,
                        headers={"Content-Type": "application/xml"},
                    )
                    if r.status_code in (200, 201):
                        logger.info(f"Applied style '{ws}:{style_name}' to layer '{coverage_name}'")
                    else:
                        logger.warning(
                            f"Could not apply style to layer '{coverage_name}': "
                            f"{r.status_code} {r.text}"
                        )

            return True


# Singleton
geoserver = GeoServerClient(
    GEOSERVER_URL,
    GEOSERVER_USER,
    GEOSERVER_PASSWORD,
    GEOSERVER_WORKSPACE,
)


# ===================================================================
# Entity → layer info
# ===================================================================

def derive_layer_info(entity: dict) -> Optional[dict]:
    """
    Read an NGSI-LD entity and return the info needed to publish it
    in GeoServer, or *None* if it should not be published.
    """
    publish = entity.get("publishToGeoserver", {}).get("value", False)
    if not publish:
        return None

    file_path = entity.get("filePath", {}).get("value")
    if not file_path:
        logger.warning(
            f"Entity {entity.get('id')} has publishToGeoserver=true "
            "but no filePath — skipping"
        )
        return None

    entity_type = entity.get("type")

    if entity_type == "GeoSpatialLayer":
        layer_type = entity.get("layerType", {}).get("value", "unknown")
        name = layer_type.lower()
        title = entity.get("name", {}).get("value", name)
        if name == "dtm":
            style = "dtm_style"
        elif name == "ndwi":
            style = "ndwi_style"
        elif name == "ndvi":
            style = "ndvi_style"
        elif name == "nir":
            style = "nir_style"
        elif name == "rgb":
            style = "rgb_style"
        elif name == "lst":
            style = "lst_style"
        else:
            style = None
    elif entity_type == "UHIHeatMap":
        name = "uhi_prediction"
        title = entity.get("name", {}).get("value", "UHI Heat Risk Prediction")
        style = "uhi_prediction_style"
    else:
        # Try to derive from geoserverLayer property
        gs_layer = entity.get("geoserverLayer", {}).get("value", "")
        if ":" in gs_layer:
            name = gs_layer.split(":", 1)[1]
        else:
            name = gs_layer or entity.get("id", "unknown").split(":")[-1]
        title = entity.get("name", {}).get("value", name)
        style = None

    geoserver_path = translate_path(file_path)

    return {
        "name": name,
        "store_name": f"store_{name}",
        "title": title,
        "geoserver_path": geoserver_path,
        "style_name": style,
    }


def sync_entity(entity: dict) -> bool:
    """Publish a single entity to GeoServer (if applicable)."""
    info = derive_layer_info(entity)
    if info is None:
        return False

    logger.info(
        f"Syncing entity {entity.get('id')} → "
        f"{GEOSERVER_WORKSPACE}:{info['name']} "
        f"(file: {info['geoserver_path']})"
    )

    # Ensure style exists in GeoServer if applicable
    if info['style_name'] and info['name'] in STYLES:
        geoserver.ensure_style(info['style_name'], STYLES[info['name']])

    return geoserver.publish_layer(
        store_name=info["store_name"],
        coverage_name=info["name"],
        title=info["title"],
        file_path=info["geoserver_path"],
        style_name=info['style_name'],
    )


# ===================================================================
# Orion-LD helpers
# ===================================================================

async def register_subscription() -> None:
    """
    Register (or re-create) the Orion-LD subscription that notifies
    this service when GeoSpatialLayer or UHIHeatMap entities change.
    """
    subscription = {
        "@context": NGSI_LD_CONTEXT,
        "id": SUBSCRIPTION_ID,
        "type": "Subscription",
        "description": "Sync publishable layers to GeoServer",
        "entities": [
            {"type": "GeoSpatialLayer"},
            {"type": "UHIHeatMap"},
        ],
        "watchedAttributes": ["publishToGeoserver", "filePath"],
        "notification": {
            "endpoint": {
                "uri": f"{SELF_URL}/sync",
                "accept": "application/json",
            }
        },
    }

    headers = {
        "Content-Type": "application/ld+json",
        "Accept": "application/ld+json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Try to create
        r = await client.post(
            f"{ORION_URL}/ngsi-ld/v1/subscriptions",
            json=subscription,
            headers=headers,
        )
        if r.status_code == 201:
            logger.info(f"Created subscription {SUBSCRIPTION_ID}")
            return

        if r.status_code == 409:
            # Already exists — delete and recreate to update endpoint / attrs
            await client.delete(
                f"{ORION_URL}/ngsi-ld/v1/subscriptions/{SUBSCRIPTION_ID}"
            )
            r = await client.post(
                f"{ORION_URL}/ngsi-ld/v1/subscriptions",
                json=subscription,
                headers=headers,
            )
            if r.status_code == 201:
                logger.info(f"Re-created subscription {SUBSCRIPTION_ID}")
                return

        logger.error(
            f"Failed to register subscription: {r.status_code} {r.text}"
        )


async def initial_sync() -> None:
    """
    Query Orion for all existing entities and sync those with
    ``publishToGeoserver=true`` to GeoServer.
    """
    logger.info("Running initial sync of existing entities …")
    synced = 0

    for entity_type in ("GeoSpatialLayer", "UHIHeatMap"):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    f"{ORION_URL}/ngsi-ld/v1/entities",
                    params={"type": entity_type, "local": "true"},
                    headers={"Accept": "application/json"},
                )
            if r.status_code != 200:
                logger.warning(
                    f"Could not query {entity_type}: {r.status_code}"
                )
                continue

            entities = r.json()
            for entity in entities:
                if sync_entity(entity):
                    synced += 1

        except Exception as exc:
            logger.warning(f"Initial sync for {entity_type} failed: {exc}")

    logger.info(f"Initial sync complete — {synced} layer(s) published")


# ===================================================================
# FastAPI app
# ===================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup sequence: GeoServer ready → workspace → sync → subscribe."""
    logger.info("Starting GeoServer Sync Service")
    logger.info(f"  Orion URL        : {ORION_URL}")
    logger.info(f"  GeoServer URL    : {GEOSERVER_URL}")
    logger.info(f"  Workspace        : {GEOSERVER_WORKSPACE}")
    logger.info(f"  Path mappings    : {PATH_MAPPINGS}")

    # Run blocking GeoServer readiness check in a thread
    await asyncio.to_thread(geoserver.wait_until_ready)
    await asyncio.to_thread(geoserver.ensure_workspace)

    # Initial sync + subscription (Orion may not be ready yet — retry)
    for attempt in range(10):
        try:
            await initial_sync()
            await register_subscription()
            break
        except Exception as exc:
            logger.warning(
                f"Startup sync/subscribe attempt {attempt + 1} failed: {exc}"
            )
            await asyncio.sleep(5)

    yield
    logger.info("Shutting down GeoServer Sync Service")


app = FastAPI(
    title="GeoServer Sync Service",
    description=(
        "Keeps GeoServer in sync with Orion-LD entities. "
        "Layers with publishToGeoserver=true are automatically published."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ===================================================================
# Pydantic models
# ===================================================================

class NotificationData(BaseModel):
    """Orion-LD notification payload."""
    id: str
    type: str
    subscriptionId: Optional[str] = None
    notifiedAt: Optional[str] = None
    data: list[dict] = []


# ===================================================================
# Endpoints
# ===================================================================

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "geoserver-sync"}


@app.post("/sync")
async def handle_notification(notification: NotificationData):
    """
    Receive an Orion-LD notification and sync the affected entities
    to GeoServer.
    """
    logger.info(
        f"Received notification {notification.id} "
        f"with {len(notification.data)} entit(ies)"
    )

    results = []
    for entity in notification.data:
        entity_id = entity.get("id", "?")
        ok = await asyncio.to_thread(sync_entity, entity)
        results.append({"entity": entity_id, "synced": ok})
        if ok:
            logger.info(f"  ✓ Synced {entity_id}")
        else:
            logger.info(f"  – Skipped {entity_id} (publishToGeoserver != true or no filePath)")

    return {"status": "ok", "results": results}


@app.post("/sync/all")
async def force_sync_all():
    """Force a full re-sync of all Orion entities to GeoServer."""
    await initial_sync()
    return {"status": "ok", "message": "Full re-sync completed"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

