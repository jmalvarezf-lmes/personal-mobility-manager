"""
Presentation: Parking API router.

Exposes GET /parking/ser-zone to find the nearest SER zone for a coordinate.
"""

from fastapi import APIRouter, HTTPException, Query, Request
from shapely.geometry import Point

from mobility_manager.domain.exceptions import SerZoneNotFoundError
from mobility_manager.domain.value_objects.location import GeoLocation, _wgs84_to_utm
from mobility_manager.presentation.api.limiter import limiter
from mobility_manager.presentation.api.schemas import SerZoneResponse

router = APIRouter(prefix="/parking", tags=["parking"])


@router.get("/ser-zone", response_model=SerZoneResponse)
@limiter.limit("60/minute")
def get_ser_zone(
    request: Request,
    lat: float = Query(..., ge=-90, le=90, description="Latitude (WGS84)"),
    lng: float = Query(..., ge=-180, le=180, description="Longitude (WGS84)"),
) -> SerZoneResponse:
    """Find the nearest SER parking zone for the given coordinates, including street names."""
    use_case = request.app.state.find_nearest_ser_zone
    repo = request.app.state.ser_zone_repo
    location = GeoLocation(lat=lat, lng=lng)

    try:
        ser_zone = use_case.execute(location)
    except SerZoneNotFoundError:
        raise HTTPException(status_code=404, detail="No SER zone data available") from None

    # Zero distance if location falls inside the zone's polygon (see design.md D5/D6);
    # otherwise the exact UTM distance to the polygon boundary, rounded to the nearest integer.
    utm_x, utm_y = _wgs84_to_utm.transform(lng, lat)
    distance = int(round(ser_zone.geometry.distance(Point(utm_x, utm_y))))

    street_names = repo.get_street_names(ser_zone.city_code, ser_zone.zone_number, ser_zone.zone_type)
    zone_area = repo.get_zone_area(ser_zone.city_code, ser_zone.zone_number)

    return SerZoneResponse(
        zone_number=ser_zone.zone_number,
        zone_type=ser_zone.zone_type,
        district=ser_zone.district,
        neighbourhood=zone_area.neighbourhood if zone_area is not None else None,
        street_names=street_names,
        spot_count=ser_zone.spot_count,
        distance_meters=distance,
    )
