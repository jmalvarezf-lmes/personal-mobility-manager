"""
Presentation: Cities API router.

Exposes GET /cities to list every row in the `cities` table — the live
source of truth for which cities are registered (see city-registry
spec.md). No authentication required.
"""

from fastapi import APIRouter, Request

from mobility_manager.presentation.api.schemas import CityResponse

router = APIRouter(tags=["cities"])


@router.get("/cities", response_model=list[CityResponse])
def list_cities(request: Request) -> list[CityResponse]:
    """Return every row in the `cities` table."""
    repo = request.app.state.city_repo
    return [CityResponse(code=c.code, name=c.name) for c in repo.list_all()]
