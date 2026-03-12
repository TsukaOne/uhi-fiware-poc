"""
VLINDER API Router — exposes the reference temperature endpoint.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from algorithm.infrastructure.vlinder_client import VlinderClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vlinder", tags=["vlinder"])


class TBaseResponse(BaseModel):
    value: float
    station_id: str
    station_name: str
    timestamp: str
    fallback: bool


def _get_vlinder_client() -> VlinderClient:
    from main import vlinder_client
    return vlinder_client


@router.get("/t_base", response_model=TBaseResponse)
async def get_t_base(
    client: VlinderClient = Depends(_get_vlinder_client),
):
    """Return the current reference temperature from the VLINDER network."""
    reading = await client.get_t_base()
    return TBaseResponse(
        value=reading.value,
        station_id=reading.station_id,
        station_name=reading.station_name,
        timestamp=reading.timestamp,
        fallback=reading.fallback,
    )
