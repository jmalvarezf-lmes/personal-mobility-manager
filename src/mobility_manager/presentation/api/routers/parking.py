"""
Presentation: Parking API router.

Exposes GET /parking/ser-zone to find the nearest SER zone for a coordinate.
"""
from fastapi import APIRouter, HTTPException, Query, Request

from mobility_manager.domain.exceptions import SerZoneNotFoundError
from mobility_manager.presentation.api.limiter import limiter
from mobility_manager.domain.value_objects.location import GeoLocation
from mobility_manager.infrastructure.repositories.postgres.ser_zone_repo import (
    distance_m,
)
from mobility_manager.presentation.api.schemas import SerZoneResponse

router = APIRouter(prefix="/parking", tags=["parking"])


@router.get("/ser-zone", response_model=SerZoneResponse)
@limiter.limit("60/minute")
def get_ser_zone(
    request: Request,
    lat: float = Query(..., ge=-90, le=90, description="Latitude (WGS84)"),
    lng: float = Query(..., ge=-180, le=180, description="Longitude (WGS84)"),
) -> SerZoneResponse:
    """Find the nearest Madrid SER parking zone for the given coordinates."""
    use_case = request.app.state.find_nearest_ser_zone
    location = GeoLocation(lat=lat, lng=lng)

    try:
        ser_zone = use_case.execute(location)
    except SerZoneNotFoundError:
        raise HTTPException(status_code=404, detail="No SER zone data available")

    distance = int(
        distance_m(lat, lng, ser_zone.location.lat, ser_zone.location.lng)
    )
    return SerZoneResponse(
        street_name=ser_zone.street_name,
        zone_code=ser_zone.zone_code,
        zone_label=ser_zone.zone_label,
        distance_meters=distance,
        latitude=ser_zone.location.lat,
        longitude=ser_zone.location.lng,
    )
