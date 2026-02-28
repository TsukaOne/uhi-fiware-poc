"""
Orion-LD HTTP client for the prediction service.

"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from algorithm.config import Settings

logger = logging.getLogger(__name__)


# ── Domain exceptions ────────────────────────────────────────────────────────

class OrionError(Exception):
    """Base for all Orion communication errors."""


class OrionEntityNotFound(OrionError):
    """Entity does not exist in Orion."""


class OrionUnavailable(OrionError):
    """Orion broker is unreachable or timed out."""


class OrionUnexpectedResponse(OrionError):
    """Orion returned an unexpected HTTP status."""


# ── Client ───────────────────────────────────────────────────────────────────

class OrionClient:
    """
    Async HTTP client for the Orion-LD Context Broker.
    """

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.orion_url.rstrip("/")
        self._timeout = settings.orion_timeout
        self._context = settings.ngsi_ld_context
        self._ld_headers = {
            "Content-Type": "application/ld+json",
            "Accept": "application/ld+json",
        }

    # ── Queries ──────────────────────────────────────────────────────

    async def get_entity(self, entity_id: str) -> dict[str, Any]:
        """
        Fetch a single NGSI-LD entity by ID.

        """
        url = f"{self._base_url}/ngsi-ld/v1/entities/{entity_id}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    url,
                    params={"local": "true"},
                    headers={"Accept": "application/json"},
                )
        except httpx.ConnectError as exc:
            raise OrionUnavailable(
                f"Cannot connect to Orion at {self._base_url}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise OrionUnavailable(
                f"Timeout connecting to Orion at {self._base_url}"
            ) from exc

        if response.status_code == 404:
            raise OrionEntityNotFound(
                f"Entity '{entity_id}' not found in Orion. "
                "Has the ingestion pipeline run?"
            )
        if response.status_code != 200:
            raise OrionUnexpectedResponse(
                f"Orion returned {response.status_code} for '{entity_id}': "
                f"{response.text}"
            )

        return response.json()

    # ── Mutations ────────────────────────────────────────────────────

    async def upsert_entity(self, entity: dict[str, Any]) -> str:
        """
        Create or update an entity in Orion.

        Returns the entity ID.
        """
        entity_id: str = entity["id"]
        payload = {**entity, "@context": self._context}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/ngsi-ld/v1/entities",
                json=payload,
                headers=self._ld_headers,
            )

            if response.status_code == 201:
                logger.info(f"Created entity: {entity_id}")
                return entity_id

            if response.status_code == 409:
                return await self._patch_attrs(client, entity_id, payload)

        raise OrionUnexpectedResponse(
            f"Failed to upsert '{entity_id}': "
            f"{response.status_code} {response.text}"
        )

    async def _patch_attrs(
        self,
        client: httpx.AsyncClient,
        entity_id: str,
        entity: dict[str, Any],
    ) -> str:
        """PATCH the attributes of an existing entity"""
        patch_body = {
            k: v for k, v in entity.items()
            if k not in ("id", "type")
        }
        patch_body["@context"] = self._context

        response = await client.patch(
            f"{self._base_url}/ngsi-ld/v1/entities/{entity_id}/attrs",
            json=patch_body,
            headers=self._ld_headers,
        )

        if response.status_code in (200, 204):
            logger.info(f"Updated entity: {entity_id}")
            return entity_id

        raise OrionUnexpectedResponse(
            f"Failed to patch '{entity_id}': "
            f"{response.status_code} {response.text}"
        )

    async def upsert_subscription(self, subscription: dict[str, Any]) -> None:
        """
        Register or refresh a subscription..
        """
        subscription_id: str = subscription["id"]
        payload = {**subscription, "@context": self._context}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/ngsi-ld/v1/subscriptions",
                json=payload,
                headers=self._ld_headers,
            )

            if response.status_code == 201:
                logger.info(f"Created subscription: {subscription_id}")
                return

            if response.status_code == 409:
                await client.delete(
                    f"{self._base_url}/ngsi-ld/v1/subscriptions/{subscription_id}"
                )
                response = await client.post(
                    f"{self._base_url}/ngsi-ld/v1/subscriptions",
                    json=payload,
                    headers=self._ld_headers,
                )
                if response.status_code == 201:
                    logger.info(f"Re-created subscription: {subscription_id}")
                    return

        raise OrionUnexpectedResponse(
            f"Failed to register subscription '{subscription_id}': "
            f"{response.status_code} {response.text}"
        )