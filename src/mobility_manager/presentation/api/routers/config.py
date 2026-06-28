"""
Presentation: Config API router.

Exposes GET /config to provide runtime configuration values to the frontend.
"""

from fastapi import APIRouter

from mobility_manager.config import get_osm_tile_url
from mobility_manager.presentation.api.schemas import ConfigResponse

router = APIRouter(tags=["config"])


@router.get("/config", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    """Return runtime configuration for the frontend."""
    return ConfigResponse(osm_tile_url=get_osm_tile_url())
