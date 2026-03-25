"""
API request/response models.
"""

from typing import Optional
from pydantic import BaseModel


class IngestRequest(BaseModel):
    """Optional per-request URL overrides for each data source."""
    rgb_url: Optional[str] = None
    nir_url: Optional[str] = None
    dtm_url: Optional[str] = None
    buildings_and_engineering_works_url: Optional[str] = None


class IngestResponse(BaseModel):
    status: str
    message: str
    layers: list[str] = []


class LayerInfo(BaseModel):
    id: str
    name: str
    layer_type: str
    file_path: str
    geoserver_layer: str
