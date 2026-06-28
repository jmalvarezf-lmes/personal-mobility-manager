"""
Presentation: Vehicles API router.

Endpoints:
  POST   /vehicles                       — register a new vehicle
  GET    /vehicles/{vehicle_id}/location — latest known location
  POST   /vehicles/{token}/location      — push ingest from generic device
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from mobility_manager.domain.exceptions import (
    BrandNotEnabledError,
    VehicleLocationNotFoundError,
)
from mobility_manager.domain.value_objects.toyota_config import ToyotaConfig
from mobility_manager.presentation.api.limiter import limiter
from mobility_manager.presentation.api.schemas import (
    PushLocationRequest,
    RegisterToyotaRequest,
    RegisterVehicleRequest,
    VehicleLocationResponse,
    VehicleResponse,
)

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.post("", response_model=VehicleResponse, status_code=201)
def register_vehicle(
    request: Request,
    body: RegisterVehicleRequest,
) -> VehicleResponse:
    """Register a new vehicle and return its ID (and token for Generic brand)."""
    use_case = request.app.state.register_vehicle

    toyota_config = None
    if isinstance(body, RegisterToyotaRequest):
        toyota_config = ToyotaConfig(
            username=body.username,
            password=body.password,
            locale=body.locale,
            vin=body.vin,
        )

    try:
        result = use_case.execute(
            brand=body.brand,
            display_name=body.display_name,
            vin=getattr(body, "vin", None),
            toyota_config=toyota_config,
        )
    except BrandNotEnabledError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return VehicleResponse(
        vehicle_id=result.vehicle_id,
        brand=result.brand,
        display_name=result.display_name,
        vin=result.vin,
        location_token=result.location_token,
    )


@router.get("/{vehicle_id}/location", response_model=VehicleLocationResponse)
def get_latest_location(request: Request, vehicle_id: UUID) -> VehicleLocationResponse:
    """Return the most recent known GPS location for the given vehicle."""
    use_case = request.app.state.get_latest_vehicle_location

    try:
        location = use_case.execute(vehicle_id)
    except VehicleLocationNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="No location history found for this vehicle",
        ) from None

    return VehicleLocationResponse(
        vehicle_id=location.vehicle_id,
        latitude=location.latitude,
        longitude=location.longitude,
        recorded_at=location.recorded_at,
        received_at=location.received_at,
        source=location.source,
    )


@router.post("/{token}/location", status_code=204)
@limiter.limit("60/minute")
def push_vehicle_location(
    request: Request,
    token: str,
    body: PushLocationRequest,
) -> Response:
    """
    Accept a GPS location push from a generic vehicle device.

    Token ownership is the sole authorization mechanism — no auth header required.
    Returns 204 No Content on success.
    """
    config_repo = request.app.state.vehicle_config_repo

    vehicle_id = config_repo.find_vehicle_by_token(token)
    if vehicle_id is None:
        raise HTTPException(status_code=404, detail="Unknown token")

    record_use_case = request.app.state.record_vehicle_location

    try:
        record_use_case.execute(
            vehicle_id=vehicle_id,
            lat=body.lat,
            lon=body.lon,
            recorded_at=body.recorded_at,
            source="push",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return Response(status_code=204)
