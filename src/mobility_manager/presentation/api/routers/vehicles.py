"""
Presentation: Vehicles API router.

Endpoints:
  POST   /vehicles                       — register a new vehicle
  GET    /vehicles/{vehicle_id}/location — latest known location
  POST   /vehicles/{token}/location      — push ingest from generic device
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from mobility_manager.domain.entities.user import User
from mobility_manager.domain.exceptions import (
    BrandNotEnabledError,
    VehicleLocationNotFoundError,
    VehicleNotFoundError,
)
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.domain.value_objects.toyota_config import ToyotaConfig
from mobility_manager.presentation.api.deps import get_current_user
from mobility_manager.presentation.api.limiter import limiter
from mobility_manager.presentation.api.schemas import (
    GenericConfigResponse,
    PushLocationRequest,
    RegisterToyotaRequest,
    RegisterVehicleRequest,
    ToyotaConfigResponse,
    UpdateToyotaRequest,
    UpdateVehicleRequest,
    VehicleDetailResponse,
    VehicleListItem,
    VehicleLocationResponse,
    VehicleLocationSummary,
    VehicleResponse,
)

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("", response_model=list[VehicleListItem])
def list_vehicles(
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> list[VehicleListItem]:
    """Return all vehicles owned by the authenticated user."""
    result = request.app.state.list_user_vehicles.execute(current_user.id)
    items: list[VehicleListItem] = []
    for item in result:
        location_summary = None
        if item.location is not None:
            location_summary = VehicleLocationSummary(
                latitude=item.location.latitude,
                longitude=item.location.longitude,
                recorded_at=item.location.recorded_at,
            )
        items.append(
            VehicleListItem(
                vehicle_id=item.vehicle.id,
                brand=item.vehicle.brand,
                display_name=item.vehicle.display_name,
                vin=item.vehicle.vin,
                location=location_summary,
            )
        )
    return items


def _build_vehicle_detail(vehicle, config_repo) -> VehicleDetailResponse:  # type: ignore[no-untyped-def]
    """Build a VehicleDetailResponse from a vehicle entity and its config repo."""
    if vehicle.brand == Brand.TOYOTA:
        toyota = config_repo.get_toyota_config(vehicle.id)
        config: ToyotaConfigResponse | GenericConfigResponse = ToyotaConfigResponse(
            username=toyota.username,
            locale=toyota.locale,
        )
    else:
        generic = config_repo.get_generic_config(vehicle.id)
        token = generic.location_token if generic is not None else ""
        config = GenericConfigResponse(location_token=token)
    return VehicleDetailResponse(
        vehicle_id=vehicle.id,
        brand=vehicle.brand,
        display_name=vehicle.display_name,
        vin=vehicle.vin,
        config=config,
    )


@router.get("/{vehicle_id}", response_model=VehicleDetailResponse)
def get_vehicle(
    request: Request,
    vehicle_id: UUID,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> VehicleDetailResponse:
    """Return full detail for a specific vehicle owned by the authenticated user."""
    vehicle_repo = request.app.state.vehicle_repo
    vehicle = vehicle_repo.get_by_id(vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if vehicle.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not own this vehicle")
    return _build_vehicle_detail(vehicle, request.app.state.vehicle_config_repo)


@router.delete("/{vehicle_id}", status_code=204)
def delete_vehicle(
    request: Request,
    vehicle_id: UUID,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Response:
    """Delete a vehicle owned by the authenticated user."""
    vehicle_repo = request.app.state.vehicle_repo
    vehicle = vehicle_repo.get_by_id(vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if vehicle.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not own this vehicle")
    try:
        request.app.state.delete_vehicle.execute(vehicle_id)
    except VehicleNotFoundError:
        raise HTTPException(status_code=404, detail="Vehicle not found") from None
    return Response(status_code=204)


@router.put("/{vehicle_id}", response_model=VehicleDetailResponse)
def update_vehicle(
    request: Request,
    vehicle_id: UUID,
    body: UpdateVehicleRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> VehicleDetailResponse:
    """Update display_name (and Toyota credentials when a new password is supplied)."""
    vehicle_repo = request.app.state.vehicle_repo
    vehicle = vehicle_repo.get_by_id(vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if vehicle.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not own this vehicle")

    password = body.password if isinstance(body, UpdateToyotaRequest) else None
    username = body.username if isinstance(body, UpdateToyotaRequest) else None
    locale = body.locale if isinstance(body, UpdateToyotaRequest) else None

    try:
        request.app.state.update_vehicle.execute(
            vehicle_id=vehicle_id,
            display_name=body.display_name,
            username=username,
            locale=locale,
            password=password,
        )
    except VehicleNotFoundError:
        raise HTTPException(status_code=404, detail="Vehicle not found") from None

    # Re-fetch the updated vehicle to build the response
    updated_vehicle = vehicle_repo.get_by_id(vehicle_id)
    if updated_vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found after update")
    return _build_vehicle_detail(updated_vehicle, request.app.state.vehicle_config_repo)


@router.post("", response_model=VehicleResponse, status_code=201)
def register_vehicle(
    request: Request,
    body: RegisterVehicleRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
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
            user_id=current_user.id,
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
def get_latest_location(
    request: Request,
    vehicle_id: UUID,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> VehicleLocationResponse:
    """Return the most recent known GPS location for the given vehicle."""
    vehicle_repo = request.app.state.vehicle_repo
    vehicle = vehicle_repo.find_by_id(vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if vehicle.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not own this vehicle")

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
