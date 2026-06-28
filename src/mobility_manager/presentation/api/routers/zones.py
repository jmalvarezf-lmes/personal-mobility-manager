"""
Presentation: Zones API router.

Exposes GET /parking/ser-zones to return all stored SER zones for a city,
suitable for bulk map rendering.
"""

from fastapi import APIRouter, HTTPException, Query, Request

from mobility_manager.infrastructure.parking_services.madrid.zone_type import (
    MadridZoneType,
)
from mobility_manager.presentation.api.schemas import ListSerZonesResponse, SerZoneMapItem

router = APIRouter(prefix="/parking", tags=["parking"])

_SUPPORTED_CITIES = {"madrid"}


def _resolve_colour(city: str, zone_type_str: str) -> str:
    if city == "madrid":
        zt = MadridZoneType.from_raw(zone_type_str)
        return zt.colour if zt is not None else "#6B7280"
    return "#6B7280"


@router.get("/ser-zones", response_model=ListSerZonesResponse)
def list_ser_zones(
    request: Request,
    city: str = Query(..., description="City code (e.g. 'madrid')"),
) -> ListSerZonesResponse:
    """Return all SER zones for the given city."""
    if city not in _SUPPORTED_CITIES:
        raise HTTPException(status_code=404, detail=f"City '{city}' is not supported")

    repo = request.app.state.ser_zone_repo
    zones = repo.list_all()

    return ListSerZonesResponse(
        city=city,
        zones=[
            SerZoneMapItem(
                street_name=z.street_name,
                zone_type=z.zone_type,
                colour=_resolve_colour(city, z.zone_type),
                spot_count=z.spot_count,
                lat=z.location.lat,
                lng=z.location.lng,
            )
            for z in zones
        ],
    )
