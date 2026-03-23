"""
GeoServer REST client.

Wraps all interactions with the GeoServer REST API:
  - Readiness check
  - Workspace management
  - SLD style management
  - GeoTIFF coverage publication
"""
import logging
import time
from typing import Optional
from xml.sax.saxutils import escape as xml_escape

import httpx

logger = logging.getLogger(__name__)


class GeoServerClient:
    """Thin wrapper around the GeoServer REST API."""

    def __init__(self, base_url: str, user: str, password: str, workspace: str):
        self.base_url  = base_url.rstrip("/")
        self.auth      = (user, password)
        self.workspace = workspace

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=30.0, auth=self.auth, follow_redirects=True)

    def _rest(self, path: str) -> str:
        """Build a full REST URL."""
        return f"{self.base_url}/rest/{path}"

    def _ws_rest(self, path: str) -> str:
        """Build a REST URL scoped to the current workspace."""
        return self._rest(f"workspaces/{self.workspace}/{path}")

    # -------------------------------------------------------------------------
    # Readiness
    # -------------------------------------------------------------------------

    def wait_until_ready(self, timeout: int = 180) -> None:
        """Block until the GeoServer REST API responds."""
        logger.info("Waiting for GeoServer at %s …", self.base_url)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with self._client() as c:
                    if c.get(self._rest("about/version.json")).status_code == 200:
                        logger.info("GeoServer is ready")
                        return
            except Exception:
                pass
            time.sleep(3)
        raise RuntimeError(
            f"GeoServer at {self.base_url} did not become ready within {timeout}s"
        )

    # -------------------------------------------------------------------------
    # Workspace
    # -------------------------------------------------------------------------

    def ensure_workspace(self) -> None:
        """Create the workspace if it does not exist yet."""
        ws = self.workspace
        with self._client() as c:
            if c.get(self._rest(f"workspaces/{ws}")).status_code == 200:
                logger.info("Workspace '%s' already exists", ws)
                return

            xml = f"<workspace><name>{ws}</name></workspace>"
            r = c.post(self._rest("workspaces"), content=xml,
                       headers={"Content-Type": "application/xml"})
            if r.status_code == 201:
                logger.info("Workspace '%s' created", ws)
            else:
                logger.error("Failed to create workspace: %s %s", r.status_code, r.text)

    # -------------------------------------------------------------------------
    # SLD styles
    # -------------------------------------------------------------------------

    def ensure_style(self, style_name: str, sld_content: str) -> bool:
        """Create or update an SLD style in the workspace.

        Also handles the case of a corrupt style on the GeoServer side (HTTP 500).
        Returns True on success.
        """
        ws        = self.workspace
        style_url = self._ws_rest(f"styles/{style_name}")
        sld_bytes = sld_content.encode("utf-8")
        xml_ct    = {"Content-Type": "application/xml"}
        sld_ct    = {"Content-Type": "application/vnd.ogc.sld+xml"}

        with self._client() as c:
            r = c.get(style_url)

            # --- Corrupt style: GeoServer returns 500 ------------------------
            if r.status_code == 500:
                logger.warning("Style '%s' returned 500 — attempting recovery", style_name)
                del_r = c.delete(style_url, params={"purge": "true", "recurse": "true"})

                if del_r.status_code not in (200, 404):
                    # Cannot delete — overwrite via direct PUT
                    logger.warning(
                        "Could not delete corrupt style '%s' (%s) — attempting direct PUT",
                        style_name, del_r.status_code,
                    )
                    r2 = c.put(style_url, content=sld_bytes, headers=sld_ct)
                    if r2.status_code in (200, 201):
                        logger.info("Corrupt style '%s:%s' overwritten via PUT", ws, style_name)
                        return True
                    logger.error("PUT failed: %s %s", r2.status_code, r2.text)
                    return False

                # Deletion succeeded — treat as non-existent
                r = None

            # --- Existing style: update --------------------------------------
            if r is not None and r.status_code == 200:
                r2 = c.put(style_url, content=sld_bytes, headers=sld_ct)
                if r2.status_code in (200, 201):
                    logger.info("Style '%s:%s' updated", ws, style_name)
                    return True
                logger.error(
                    "Failed to update style '%s': %s %s",
                    style_name, r2.status_code, r2.text,
                )
                return False

            # --- Missing style: create in 2 steps ----------------------------
            # Step 1: declare the style name
            descriptor_xml = (
                f"<style>"
                f"  <name>{style_name}</name>"
                f"  <filename>{style_name}.sld</filename>"
                f"</style>"
            )
            r_declare = c.post(
                self._ws_rest("styles"),
                content=descriptor_xml.encode("utf-8"),
                headers=xml_ct,
            )
            if r_declare.status_code not in (200, 201):
                logger.error(
                    "Failed to declare style '%s': %s %s",
                    style_name, r_declare.status_code, r_declare.text,
                )
                return False

            # Step 2: upload the SLD content
            r_upload = c.put(style_url, content=sld_bytes, headers=sld_ct)
            if r_upload.status_code in (200, 201):
                logger.info("Style '%s:%s' created", ws, style_name)
                return True
            logger.error(
                "Failed to upload SLD for '%s': %s %s",
                style_name, r_upload.status_code, r_upload.text,
            )
            return False

    # -------------------------------------------------------------------------
    # GeoTIFF layer publication
    # -------------------------------------------------------------------------

    def publish_layer(
        self,
        store_name:    str,
        coverage_name: str,
        title:         str,
        file_path:     str,
        style_name:    Optional[str] = None,
    ) -> bool:
        """Idempotently publish a GeoTIFF in GeoServer.

        Creates or updates: coverage store → coverage → applies the style.
        Returns True on success.
        """
        ws         = self.workspace
        safe_title = xml_escape(title)

        with self._client() as c:
            # -----------------------------------------------------------------
            # 1) Coverage store — create or update
            # -----------------------------------------------------------------
            store_url = self._ws_rest(f"coveragestores/{store_name}")
            store_xml = (
                f"<coverageStore>"
                f"  <name>{store_name}</name>"
                f"  <workspace><name>{ws}</name></workspace>"
                f"  <enabled>true</enabled>"
                f"  <type>GeoTIFF</type>"
                f"  <url>file:{file_path}</url>"
                f"</coverageStore>"
            )
            xml_ct = {"Content-Type": "application/xml"}

            if c.get(store_url).status_code != 200:
                r = c.post(self._ws_rest("coveragestores"), content=store_xml, headers=xml_ct)
                if r.status_code not in (200, 201):
                    logger.error(
                        "Failed to create store '%s': %s %s",
                        store_name, r.status_code, r.text,
                    )
                    return False
                logger.info("Coverage store '%s' created", store_name)
            else:
                r = c.put(store_url, content=store_xml, headers=xml_ct)
                if r.status_code in (200, 201):
                    logger.info("Coverage store '%s' updated", store_name)

            # -----------------------------------------------------------------
            # 2) Coverage — create if missing
            # -----------------------------------------------------------------
            cov_url = self._ws_rest(
                f"coveragestores/{store_name}/coverages/{coverage_name}"
            )
            cov_xml = (
                f"<coverage>"
                f"  <name>{coverage_name}</name>"
                f"  <title>{safe_title}</title>"
                f"  <enabled>true</enabled>"
                f"</coverage>"
            )

            if c.get(cov_url).status_code != 200:
                r = c.post(
                    self._ws_rest(f"coveragestores/{store_name}/coverages"),
                    content=cov_xml,
                    headers=xml_ct,
                )
                if r.status_code != 201:
                    logger.error(
                        "Failed to publish coverage '%s': %s %s",
                        coverage_name, r.status_code, r.text,
                    )
                    return False
                logger.info("Coverage '%s:%s' published", ws, coverage_name)
            else:
                logger.info("Coverage '%s:%s' already exists", ws, coverage_name)

            # -----------------------------------------------------------------
            # 3) Layer — verify existence; recreate if missing
            # -----------------------------------------------------------------
            layer_url = self._rest(f"layers/{ws}:{coverage_name}")

            if c.get(layer_url).status_code != 200:
                logger.warning(
                    "Layer '%s:%s' missing — deleting and recreating coverage",
                    ws, coverage_name,
                )
                del_r = c.delete(
                    self._ws_rest(
                        f"coveragestores/{store_name}/coverages/{coverage_name}?recurse=true"
                    )
                )
                if del_r.status_code not in (200, 202):
                    logger.error(
                        "Failed to delete coverage: %s %s",
                        del_r.status_code, del_r.text,
                    )
                    return False

                r = c.post(
                    self._ws_rest(f"coveragestores/{store_name}/coverages"),
                    content=cov_xml,
                    headers=xml_ct,
                )
                if r.status_code != 201:
                    logger.error(
                        "Failed to recreate coverage: %s %s",
                        r.status_code, r.text,
                    )
                    return False
                logger.info("Coverage + layer '%s:%s' recreated", ws, coverage_name)

            elif style_name:
                # Layer exists — apply the style
                layer_xml = (
                    f"<layer>"
                    f"  <defaultStyle>"
                    f"    <name>{style_name}</name>"
                    f"    <workspace>{ws}</workspace>"
                    f"  </defaultStyle>"
                    f"</layer>"
                )
                r = c.put(layer_url, content=layer_xml, headers=xml_ct)
                if r.status_code in (200, 201):
                    logger.info(
                        "Style '%s:%s' applied to layer '%s'",
                        ws, style_name, coverage_name,
                    )
                else:
                    logger.warning(
                        "Could not apply style to layer '%s': %s %s",
                        coverage_name, r.status_code, r.text,
                    )

            return True
