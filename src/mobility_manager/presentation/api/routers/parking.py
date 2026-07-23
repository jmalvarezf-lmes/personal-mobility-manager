"""
Presentation: Parking API router.

Exposes:
  GET /parking/ser-zone — find the nearest SER zone for a coordinate.
  POST /parking/ser-tickets — create a SER parking ticket for an owned vehicle.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from shapely.geometry import Point

from mobility_manager.domain.entities.user import User
from mobility_manager.domain.exceptions import (
    SerProviderApiError,
    SerProviderSessionNotFoundError,
    SerProviderVehicleNotFoundError,
    SerTicketProviderNotFoundError,
    SerZoneNotFoundError,
    VehicleLocationNotFoundError,
    VehicleNotFoundError,
)
from mobility_manager.domain.value_objects.location import GeoLocation, _wgs84_to_utm
from mobility_manager.presentation.api.deps import get_current_user
from mobility_manager.presentation.api.limiter import limiter
from mobility_manager.presentation.api.schemas import (
    CreateSerTicketRequest,
    ParkingTicketResponse,
    SerZoneResponse,
)

router = APIRouter(prefix="/parking", tags=["parking"])


@router.get("/ser-zone", response_model=SerZoneResponse)
@limiter.limit("60/minute")
def get_ser_zone(
    request: Request,
    # Unused directly, but required: slowapi needs a Response object to write
    # Retry-After/X-RateLimit-* headers into, and this handler returns a
    # Pydantic model, not a Response — see limiter.py's headers_enabled note.
    # Removing this parameter turns every successful call into a 500.
    response: Response,
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


@router.post("/ser-tickets", response_model=ParkingTicketResponse, status_code=201)
@limiter.limit("60/minute")
def create_ser_ticket(
    request: Request,
    body: CreateSerTicketRequest,
    # Unused directly, but required — see get_ser_zone's identical note above.
    response: Response,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> ParkingTicketResponse:
    """
    Create a SER parking ticket for an owned vehicle.

    When both `latitude` and `longitude` are given, they're used as an
    explicit location override; when either is omitted, the vehicle's
    latest known location is used (see CreateSerTicket.execute).
    """
    use_case = request.app.state.create_ser_ticket

    location: GeoLocation | None = None
    if body.latitude is not None and body.longitude is not None:
        location = GeoLocation(lat=body.latitude, lng=body.longitude)

    try:
        ticket = use_case.execute(
            user_id=current_user.id,
            vehicle_id=body.vehicle_id,
            provider=body.provider,
            duration_minutes=body.duration_minutes,
            location=location,
        )
    except (
        VehicleNotFoundError,
        SerProviderSessionNotFoundError,
        SerZoneNotFoundError,
        VehicleLocationNotFoundError,
        SerTicketProviderNotFoundError,
    ) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SerProviderVehicleNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SerProviderApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ParkingTicketResponse(
        id=ticket.id,
        cost=ticket.cost,
        end_date=ticket.end_date,
        provider_reference=ticket.provider_reference,
        duration_minutes=ticket.duration_minutes,
    )
