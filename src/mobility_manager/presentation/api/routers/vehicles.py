"""
Presentation: Vehicles API router.

Endpoints:
  POST   /vehicles                                — register a new vehicle
  GET    /vehicles/{vehicle_id}/location           — latest known location
  GET    /vehicles/{vehicle_id}/locations          — paginated location history
  POST   /vehicles/{vehicle_id}/locations          — owner-submitted location (session auth, generic only)
  GET    /vehicles/{vehicle_id}/ser-tickets        — paginated SER ticket history
  POST   /vehicles/{token}/location                — push ingest from generic device
  GET    /vehicles/{vehicle_id}/ser-parking-exemptions    — view exemption
  POST   /vehicles/{vehicle_id}/ser-parking-exemptions    — set/replace exemption
  DELETE /vehicles/{vehicle_id}/ser-parking-exemptions    — clear exemption
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from mobility_manager.domain.entities.user import User
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.exceptions import (
    BrandNotEnabledError,
    InvalidSerParkingExemptionZoneError,
    VehicleLocationNotFoundError,
    VehicleNotFoundError,
)
from mobility_manager.domain.ports.vehicle_ambient_label_repository import (
    VehicleAmbientLabelRepository,
)
from mobility_manager.domain.value_objects.ambient_label_status import (
    AmbientLabelStatus,
)
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.presentation.api.deps import (
    get_current_user,
    get_owned_vehicle_or_raise,
    require_owned_vehicle,
)
from mobility_manager.presentation.api.factories import (
    VehicleRegisterFactory,
    VehicleUpdateFactory,
)
from mobility_manager.presentation.api.limiter import limiter
from mobility_manager.presentation.api.schemas import (
    GenericConfigResponse,
    PushLocationRequest,
    RegisterVehicleRequest,
    SerTicketHistoryResponse,
    SerTicketListItemResponse,
    SetVehicleSerParkingExemptionRequest,
    ToyotaConfigResponse,
    UpdateVehicleRequest,
    VehicleDetailResponse,
    VehicleListItem,
    VehicleLocationHistoryResponse,
    VehicleLocationResponse,
    VehicleLocationSummary,
    VehicleResponse,
    VehicleSerParkingExemptionResponse,
)

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


def _resolve_ambient_label(vehicle_id: UUID, ambient_label_repo: VehicleAmbientLabelRepository | None) -> str | None:
    """
    Return the resolved ambient label value for `vehicle_id`, or None when
    no confident result exists (no row yet, or status != found) — see
    ambient-label spec.md "Ambient label is exposed on vehicle read endpoints".
    """
    if ambient_label_repo is None:
        return None
    row = ambient_label_repo.get_by_vehicle_id(vehicle_id)
    if row is None or row.status != AmbientLabelStatus.FOUND or row.label is None:
        return None
    return row.label.value


@router.get("", response_model=list[VehicleListItem])
def list_vehicles(
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> list[VehicleListItem]:
    """Return all vehicles owned by the authenticated user."""
    result = request.app.state.list_user_vehicles.execute(current_user.id)
    ambient_label_repo = getattr(request.app.state, "vehicle_ambient_label_repo", None)
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
                license_plate=item.vehicle.license_plate,
                location=location_summary,
                ambient_label=_resolve_ambient_label(item.vehicle.id, ambient_label_repo),
                has_ser_tickets=item.has_ser_tickets,
            )
        )
    return items


def _build_vehicle_detail(vehicle, config_repo, ambient_label_repo=None) -> VehicleDetailResponse:  # type: ignore[no-untyped-def]
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
        license_plate=vehicle.license_plate,
        config=config,
        ambient_label=_resolve_ambient_label(vehicle.id, ambient_label_repo),
    )


@router.get("/{vehicle_id}", response_model=VehicleDetailResponse)
def get_vehicle(
    request: Request,
    vehicle_id: UUID,
    vehicle: Vehicle = Depends(require_owned_vehicle),  # noqa: B008
) -> VehicleDetailResponse:
    """Return full detail for a specific vehicle owned by the authenticated user."""
    ambient_label_repo = getattr(request.app.state, "vehicle_ambient_label_repo", None)
    return _build_vehicle_detail(vehicle, request.app.state.vehicle_config_repo, ambient_label_repo)


@router.delete("/{vehicle_id}", status_code=204)
def delete_vehicle(
    request: Request,
    vehicle_id: UUID,
    vehicle: Vehicle = Depends(require_owned_vehicle),  # noqa: B008
) -> Response:
    """Delete a vehicle owned by the authenticated user."""
    try:
        request.app.state.delete_vehicle.execute(vehicle_id)
    except VehicleNotFoundError:
        raise HTTPException(status_code=404, detail="Vehicle not found") from None
    return Response(status_code=204)


@router.put("/{vehicle_id}", response_model=VehicleDetailResponse)
@limiter.limit("60/minute")
def update_vehicle(
    request: Request,
    # Unused directly, but required: slowapi needs a Response object to write
    # Retry-After/X-RateLimit-* headers into, and this handler returns a
    # Pydantic model, not a Response — see limiter.py's headers_enabled note.
    # Removing this parameter turns every successful call into a 500.
    response: Response,
    vehicle_id: UUID,
    body: UpdateVehicleRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> VehicleDetailResponse:
    """Update display_name, license_plate (and Toyota credentials when a new password is supplied)."""
    # Ownership is checked here (after `body` has already been parsed and
    # validated above), not via Depends(require_owned_vehicle) — see
    # deps.py module docstring / design.md decision 5 amendment.
    get_owned_vehicle_or_raise(request, vehicle_id, current_user)
    vehicle_repo = request.app.state.vehicle_repo
    update_input = VehicleUpdateFactory.build(body)

    try:
        request.app.state.update_vehicle.execute(
            vehicle_id=vehicle_id,
            display_name=update_input.display_name,
            username=update_input.username,
            locale=update_input.locale,
            password=update_input.password,
            license_plate=update_input.license_plate,
        )
    except VehicleNotFoundError:
        raise HTTPException(status_code=404, detail="Vehicle not found") from None

    # Re-fetch the updated vehicle to build the response
    updated_vehicle = vehicle_repo.get_by_id(vehicle_id)
    if updated_vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found after update")
    ambient_label_repo = getattr(request.app.state, "vehicle_ambient_label_repo", None)
    return _build_vehicle_detail(updated_vehicle, request.app.state.vehicle_config_repo, ambient_label_repo)


@router.post("", response_model=VehicleResponse, status_code=201)
@limiter.limit("60/minute")
def register_vehicle(
    request: Request,
    # Unused directly, but required — see the identical note on update_vehicle
    # above / limiter.py's headers_enabled note.
    response: Response,
    body: RegisterVehicleRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> VehicleResponse:
    """Register a new vehicle and return its ID (and token for Generic brand)."""
    use_case = request.app.state.register_vehicle

    register_input = VehicleRegisterFactory.build(body)

    try:
        result = use_case.execute(
            brand=register_input.brand,
            display_name=register_input.display_name,
            user_id=current_user.id,
            vin=register_input.vin,
            toyota_config=register_input.toyota_config,
            license_plate=register_input.license_plate,
        )
    except BrandNotEnabledError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    ambient_label_repo = getattr(request.app.state, "vehicle_ambient_label_repo", None)
    return VehicleResponse(
        vehicle_id=result.vehicle_id,
        brand=result.brand,
        display_name=result.display_name,
        vin=result.vin,
        location_token=result.location_token,
        license_plate=result.license_plate,
        # The best-effort lookup in RegisterVehicle.execute() runs and
        # persists synchronously before returning, so a fresh read here
        # (not a value threaded through RegisterVehicleResult) already
        # reflects it — same helper used by GET /vehicles and /vehicles/{id}.
        ambient_label=_resolve_ambient_label(result.vehicle_id, ambient_label_repo),
    )


@router.get("/{vehicle_id}/location", response_model=VehicleLocationResponse)
def get_latest_location(
    request: Request,
    vehicle_id: UUID,
    vehicle: Vehicle = Depends(require_owned_vehicle),  # noqa: B008
) -> VehicleLocationResponse:
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


@router.get("/{vehicle_id}/locations", response_model=VehicleLocationHistoryResponse)
@limiter.limit("120/minute")
def list_location_history(
    request: Request,
    # Unused directly, but required — see the identical note on update_vehicle
    # above / limiter.py's headers_enabled note.
    response: Response,
    vehicle_id: UUID,
    limit: int = Query(default=5, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    vehicle: Vehicle = Depends(require_owned_vehicle),  # noqa: B008
) -> VehicleLocationHistoryResponse:
    """Return a page of the given vehicle's location history, newest first."""
    use_case = request.app.state.list_vehicle_location_history

    items, has_more = use_case.execute(vehicle_id, limit=limit, offset=offset)

    return VehicleLocationHistoryResponse(
        items=[
            VehicleLocationResponse(
                vehicle_id=item.vehicle_id,
                latitude=item.latitude,
                longitude=item.longitude,
                recorded_at=item.recorded_at,
                received_at=item.received_at,
                source=item.source,
            )
            for item in items
        ],
        has_more=has_more,
    )


@router.get("/{vehicle_id}/ser-tickets", response_model=SerTicketHistoryResponse)
@limiter.limit("120/minute")
def list_ser_tickets(
    request: Request,
    # Unused directly, but required — see the identical note on update_vehicle
    # above / limiter.py's headers_enabled note.
    response: Response,
    vehicle_id: UUID,
    limit: int = Query(default=5, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    vehicle: Vehicle = Depends(require_owned_vehicle),  # noqa: B008
) -> SerTicketHistoryResponse:
    """
    Return a page of the given vehicle's SER tickets, newest first.

    Returns every ticket regardless of `auto_created` — each item carries
    its own `auto_created` value so the client can label it (see
    add-ser-ticket-history-ui design.md D4).
    """
    use_case = request.app.state.list_ser_tickets
    city_repo = request.app.state.city_repo

    items, has_more = use_case.execute(vehicle_id, limit=limit, offset=offset)

    # One list_all() call per request (not per ticket) — cheap for the
    # small cities catalog, and keeps city-name resolution server-side (see
    # design.md D5) without a per-ticket lookup query.
    city_names = {city.code: city.name for city in city_repo.list_all()}

    return SerTicketHistoryResponse(
        items=[
            SerTicketListItemResponse(
                id=item.id,
                latitude=item.latitude,
                longitude=item.longitude,
                start_date=item.start_date,
                end_date=item.end_date,
                city_code=item.city_code,
                city_name=city_names.get(item.city_code),
                zone_number=item.zone_number,
                auto_created=item.auto_created,
            )
            for item in items
        ],
        has_more=has_more,
    )


def _vehicle_token_key(request: Request) -> str:
    """
    Rate-limit key: the vehicle's own token (path parameter), not the
    caller's IP address.

    Stacked alongside the existing per-remote-address limit on
    push_vehicle_location (see change-ser-auto-ticket-zone-gate 4R review
    fix #2 / design.md D2's "Revised after 4R review"): a single vehicle
    token pushing locations faster than 1/minute could otherwise retrigger
    SerTicketCreationTriggerHandler's zone-transition gate far more often
    than the GPS-noise floor alone was designed to tolerate, regardless of
    which IP address the pushes come from.
    """
    return str(request.path_params["token"])


@router.post("/{token}/location", status_code=204)
@limiter.limit("60/minute")
@limiter.limit("1/minute", key_func=_vehicle_token_key)
def push_vehicle_location(
    request: Request,
    token: str,
    body: PushLocationRequest,
) -> Response:
    """
    Accept a GPS location push from a generic vehicle device.

    Token ownership is the sole authorization mechanism — no auth header required.
    Returns 204 No Content on success.

    Rate-limited two ways, independently: 60/minute per remote address
    (abuse guard across tokens) and 1/minute per vehicle token (bounds how
    often a single vehicle can retrigger the zone-transition gate — see
    `_vehicle_token_key`).
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


def _owned_vehicle_id_key(request: Request) -> str:
    """
    Rate-limit key: the target vehicle's ID (path parameter), not the
    caller's IP address — the session-authenticated counterpart of
    `_vehicle_token_key` above, for the same reason: a single vehicle
    receiving location submissions faster than 1/minute could otherwise
    retrigger `SerTicketCreationTriggerHandler`'s zone-transition gate more
    often than intended, regardless of which IP address the submissions
    come from (see `_vehicle_token_key`'s docstring and design.md's
    "Rate limiting mirrors both existing precedents").
    """
    return str(request.path_params["vehicle_id"])


@router.post("/{vehicle_id}/locations", status_code=204)
@limiter.limit("60/minute")
@limiter.limit("1/minute", key_func=_owned_vehicle_id_key)
def push_vehicle_location_authenticated(
    request: Request,
    vehicle_id: UUID,
    body: PushLocationRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Response:
    """
    Accept a GPS location submission from the authenticated owner of a
    generic vehicle, via their own logged-in session — no device token
    required.

    Deliberately a distinct route from `POST /{token}/location` (plural
    `locations`, not singular `location`): `location_token` values are
    UUID-formatted, so a `{vehicle_id}` path converter on the same route
    shape as the token route would be ambiguous / could silently misroute.
    See design.md decision "Path must be `locations` (plural)...".

    Restricted to `Brand.GENERIC` vehicles — Toyota vehicles get their
    location exclusively from the Toyota backend poll, so accepting a
    manual submission for one would create a second, conflicting source of
    truth. Rejected with 400 (not 404/403 — the caller does own the
    vehicle; the request is simply invalid for this vehicle type).

    Delegates to the same `RecordVehicleLocation` use case as
    `push_vehicle_location`, with `source="push"` — persistence, dedup, and
    event semantics stay identical to the device-push path.

    Rate-limited two ways, independently, mirroring `push_vehicle_location`:
    60/minute per remote address, and 1/minute per `vehicle_id` (see
    `_owned_vehicle_id_key`).
    """
    # Ownership is checked here (after `body` has already been parsed and
    # validated above), not via Depends(require_owned_vehicle) — see
    # deps.py module docstring / design.md decision 5 amendment.
    vehicle = get_owned_vehicle_or_raise(request, vehicle_id, current_user)

    if vehicle.brand != Brand.GENERIC:
        raise HTTPException(
            status_code=400,
            detail="Only generic vehicles accept manual location submissions",
        )

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


@router.get("/{vehicle_id}/ser-parking-exemptions", response_model=VehicleSerParkingExemptionResponse)
def get_ser_parking_exemption(
    request: Request,
    vehicle_id: UUID,
    vehicle: Vehicle = Depends(require_owned_vehicle),  # noqa: B008
) -> VehicleSerParkingExemptionResponse:
    """Return the authenticated owner's vehicle's stored SER parking exemption, or nulls if unset."""
    use_case = request.app.state.get_vehicle_ser_parking_exemption
    exemption = use_case.execute(vehicle_id)
    if exemption is None:
        return VehicleSerParkingExemptionResponse(city_code=None, zone_number=None)
    return VehicleSerParkingExemptionResponse(city_code=exemption.city_code, zone_number=exemption.zone_number)


@router.post("/{vehicle_id}/ser-parking-exemptions", response_model=VehicleSerParkingExemptionResponse)
def set_ser_parking_exemption(
    request: Request,
    vehicle_id: UUID,
    body: SetVehicleSerParkingExemptionRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> VehicleSerParkingExemptionResponse:
    """Set (or replace) the authenticated owner's vehicle's SER parking exemption."""
    # Ownership is checked here (after `body` has already been parsed and
    # validated above), not via Depends(require_owned_vehicle) — see
    # deps.py module docstring / design.md decision 5 amendment.
    get_owned_vehicle_or_raise(request, vehicle_id, current_user)
    use_case = request.app.state.set_vehicle_ser_parking_exemption
    try:
        exemption = use_case.execute(vehicle_id, body.city_code, body.zone_number)
    except InvalidSerParkingExemptionZoneError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return VehicleSerParkingExemptionResponse(city_code=exemption.city_code, zone_number=exemption.zone_number)


@router.delete("/{vehicle_id}/ser-parking-exemptions", status_code=204)
def clear_ser_parking_exemption(
    request: Request,
    vehicle_id: UUID,
    vehicle: Vehicle = Depends(require_owned_vehicle),  # noqa: B008
) -> Response:
    """Clear the authenticated owner's vehicle's SER parking exemption (idempotent — 204 either way)."""
    use_case = request.app.state.clear_vehicle_ser_parking_exemption
    use_case.execute(vehicle_id)
    return Response(status_code=204)
