"""
Layer Resolver — resolves NGSI-LD entity IDs to local file paths.

Single responsibility: entity_id → validated local Path.
"""
from __future__ import annotations

import logging
from pathlib import Path

from algorithm.infrastructure.orion_client import OrionClient, OrionEntityNotFound

logger = logging.getLogger(__name__)


class MissingFilePathError(Exception):
    """Entity exists in Orion but has no filePath property."""


class EntityFileNotFoundError(Exception):
    """Entity's filePath points to a file that does not exist on disk."""


class LayerResolver:
    """
    Resolves a mapping of {layer_name: entity_id} to {layer_name: Path}.
    """

    def __init__(self, orion_client: OrionClient) -> None:
        self._orion = orion_client

    async def resolve_required(
        self, layer_entity_map: dict[str, str]
    ) -> dict[str, Path]:
        """
        Resolve all layers. Raises if any layer is missing or its file absent.

        Parameters
        ----------
        layer_entity_map : {layer_name: entity_id}

        Returns
        -------
        {layer_name: local_file_path}
        """
        logger.info(f"Resolving {len(layer_entity_map)} required layer(s) from Orion…")
        paths: dict[str, Path] = {}

        for layer_name, entity_id in layer_entity_map.items():
            entity = await self._orion.get_entity(entity_id)
            path = self._extract_and_validate_path(entity)
            paths[layer_name] = path
            logger.info(f"  {layer_name:<20} → {path}")

        return paths

    async def resolve_with_optional(
        self,
        required: dict[str, str],
        optional: dict[str, str],
    ) -> dict[str, Path]:
        """
        Resolve required layers (raises on failure) and optional layers
        (logs a warning and skips on failure).

        Used by the legacy prediction endpoint which requires NDVI
        but treats NDWI as non-blocking.
        """
        paths = await self.resolve_required(required)

        for layer_name, entity_id in optional.items():
            try:
                entity = await self._orion.get_entity(entity_id)
                path = self._extract_and_validate_path(entity)
                paths[layer_name] = path
                logger.info(f"  {layer_name:<20} → {path} (optional)")
            except OrionEntityNotFound:
                logger.warning(
                    f"  {layer_name}: entity '{entity_id}' not found — skipping"
                )
            except (MissingFilePathError, EntityFileNotFoundError) as exc:
                logger.warning(f"  {layer_name}: {exc} — skipping")

        return paths

    @staticmethod
    def _extract_and_validate_path(entity: dict) -> Path:
        """
        Extract filePath from an NGSI-LD entity and verify it exists on disk.

        Raises
        ------
        MissingFilePathError    — entity has no filePath property
        EntityFileNotFoundError — file does not exist on disk
        """
        entity_id = entity.get("id", "?")
        raw_value = entity.get("filePath", {}).get("value")

        if not raw_value:
            raise MissingFilePathError(
                f"Entity '{entity_id}' has no filePath property. "
                "Has ingestion set this attribute?"
            )

        path = Path(raw_value)
        if not path.exists():
            raise EntityFileNotFoundError(
                f"File '{path}' referenced by entity '{entity_id}' "
                "does not exist on disk."
            )

        return path