"""
Presentation: Pydantic schemas for the FastAPI API layer.
"""

import re
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pytoyoda.utils.locale import is_valid_locale

from mobility_manager.domain.value_objects.brand import Brand

# ISO 3779 shape: exactly 17 uppercase alphanumeric characters, excluding
# I, O, Q (easily confused with 1, 0 — never used in a real VIN).
_VIN_PATTERN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")


class StrictRequestModel(BaseModel):
    """
    Base class for every request-body schema.

    `extra="forbid"` rejects (422) any JSON field not declared on the model,
    instead of Pydantic v2's default of silently discarding unknown fields.
    Only request bodies inherit from this — response models stay on plain
    BaseModel, since being lenient about what we return is fine, but being
    lenient about what we accept is not (see design.md decision 1).
    """

    model_config = ConfigDict(extra="forbid")


def _validate_toyota_locale(value: str) -> str:
    """Shared `locale` check for both RegisterToyotaRequest and UpdateToyotaRequest."""
    if not is_valid_locale(value):
        raise ValueError(f"'{value}' is not a recognized locale")
    return value


class SerZoneResponse(BaseModel):
    zone_number: str
    zone_type: str
    district: str
    neighbourhood: str | None
    street_names: list[str]
    spot_count: int
    distance_meters: int


class ConfigResponse(BaseModel):
    osm_tile_url: str | None
    toyota_locale: str


class CityResponse(BaseModel):
    """One row of the `cities` catalog."""

    code: str
    name: str


class SerZoneMapItem(BaseModel):
    zone_number: str
    zone_type: str
    colour: str
    district: str
    spot_count: int
    geometry: dict[str, Any]  # GeoJSON Polygon or MultiPolygon, WGS84


class FrontierMapItem(BaseModel):
    zone_number: str
    neighbourhood: str
    geometry: dict[str, Any]  # GeoJSON Polygon or MultiPolygon, WGS84 — no colour field, see design.md D8


class ListSerZonesResponse(BaseModel):
    city: str
    zones: list[SerZoneMapItem]
    frontiers: list[FrontierMapItem]


class ZoneOptionItem(BaseModel):
    """A single zone_number/neighbourhood pair for a `<select>` option.

    Deliberately has no geometry, zone_type, colour, district, or
    spot_count — GET /parking/ser-zone-options exists specifically to avoid
    the cost of reprojecting/serializing full zone geometry when a caller
    (the SER parking exemption picker) only needs a label per zone_number.
    """

    zone_number: str
    neighbourhood: str


class ListZoneOptionsResponse(BaseModel):
    city: str
    options: list[ZoneOptionItem]


# ---------------------------------------------------------------------------
# Vehicle registration schemas (discriminated union by brand)
# ---------------------------------------------------------------------------


class BaseRegisterVehicleRequest(StrictRequestModel):
    """Common fields for all vehicle registration requests."""

    display_name: str = Field(..., max_length=100)
    license_plate: str | None = Field(None, max_length=20)


class RegisterToyotaRequest(BaseRegisterVehicleRequest):
    """Registration payload for a Toyota vehicle."""

    brand: Literal[Brand.TOYOTA]
    # min_length/max_length duplicate the exact-length check _VIN_PATTERN's
    # {17} quantifier already enforces below — kept anyway so an over/under
    # length VIN is rejected by Pydantic's own bound (consistent with every
    # sibling field in this class) before the regex validator even runs.
    vin: str = Field(..., min_length=17, max_length=17)
    username: str = Field(..., max_length=100)
    password: str = Field(..., max_length=200)
    locale: str = Field(..., max_length=100)

    @field_validator("vin")
    @classmethod
    def _validate_vin(cls, value: str) -> str:
        if not _VIN_PATTERN.match(value):
            raise ValueError("vin must be exactly 17 uppercase alphanumeric characters, excluding I, O, and Q")
        return value

    @field_validator("locale")
    @classmethod
    def _validate_locale(cls, value: str) -> str:
        return _validate_toyota_locale(value)


class RegisterGenericRequest(BaseRegisterVehicleRequest):
    """Registration payload for a generic (push-only) vehicle."""

    brand: Literal[Brand.GENERIC]


RegisterVehicleRequest = Annotated[
    RegisterToyotaRequest | RegisterGenericRequest,
    Field(discriminator="brand"),
]


class VehicleResponse(BaseModel):
    """Successful vehicle registration response."""

    vehicle_id: UUID
    brand: Brand
    display_name: str
    vin: str | None
    location_token: str | None  # populated only for Generic brand
    license_plate: str | None
    # Populated when RegisterVehicle's best-effort DGT lookup resolved
    # synchronously before this response was built; null otherwise (the
    # scheduler backfills it later). See VehicleListItem.ambient_label.
    ambient_label: str | None = None


# ---------------------------------------------------------------------------
# Location schemas
# ---------------------------------------------------------------------------


class PushLocationRequest(StrictRequestModel):
    """Push-endpoint request body — sent by a generic vehicle device."""

    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude in WGS84 degrees")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude in WGS84 degrees")
    recorded_at: datetime = Field(..., description="When the GPS fix was acquired (source device clock)")


class VehicleLocationResponse(BaseModel):
    """Latest known location for a vehicle."""

    vehicle_id: UUID
    latitude: float
    longitude: float
    recorded_at: datetime
    received_at: datetime
    source: Literal["pull", "push"]


class VehicleLocationHistoryResponse(BaseModel):
    """A page of a vehicle's location history, newest first."""

    items: list[VehicleLocationResponse]
    has_more: bool


# ---------------------------------------------------------------------------
# Vehicle list / detail schemas (GET /vehicles, GET /vehicles/{id})
# ---------------------------------------------------------------------------


class VehicleLocationSummary(BaseModel):
    """Condensed location snapshot embedded in vehicle list items."""

    latitude: float
    longitude: float
    recorded_at: datetime


class VehicleListItem(BaseModel):
    """Single entry in the authenticated user's vehicle list."""

    vehicle_id: UUID
    brand: Brand
    display_name: str
    vin: str | None
    license_plate: str | None
    location: VehicleLocationSummary | None
    # The resolved DGT ambient label ("A"/"B"/"C"/"ECO"/"0"), or null when
    # no confident result exists yet (no lookup attempted, or the last
    # attempt was not_found/error — see ambient-label spec.md).
    ambient_label: str | None = None


class ToyotaConfigResponse(BaseModel):
    """Toyota configuration returned to the owner (password always masked)."""

    username: str
    locale: str
    password: str = "●●●●●●●●"


class GenericConfigResponse(BaseModel):
    """Generic vehicle configuration returned to the owner."""

    location_token: str


class VehicleDetailResponse(BaseModel):
    """Full vehicle detail including brand-specific config."""

    vehicle_id: UUID
    brand: Brand
    display_name: str
    vin: str | None
    license_plate: str | None
    config: ToyotaConfigResponse | GenericConfigResponse
    # See VehicleListItem.ambient_label.
    ambient_label: str | None = None


# ---------------------------------------------------------------------------
# Vehicle update schemas (PUT /vehicles/{id})
# ---------------------------------------------------------------------------


class BaseUpdateVehicleRequest(StrictRequestModel):
    """Common fields for all vehicle update requests."""

    display_name: str = Field(..., max_length=100)
    license_plate: str | None = Field(None, max_length=20)


class UpdateToyotaRequest(BaseUpdateVehicleRequest):
    """Update payload for a Toyota vehicle."""

    brand: Literal[Brand.TOYOTA]
    username: str = Field(..., max_length=100)
    locale: str = Field(..., max_length=100)
    password: str | None = Field(None, max_length=200)

    @field_validator("locale")
    @classmethod
    def _validate_locale(cls, value: str) -> str:
        return _validate_toyota_locale(value)


class UpdateGenericRequest(BaseUpdateVehicleRequest):
    """Update payload for a generic vehicle."""

    brand: Literal[Brand.GENERIC]


UpdateVehicleRequest = Annotated[
    UpdateToyotaRequest | UpdateGenericRequest,
    Field(discriminator="brand"),
]


# ---------------------------------------------------------------------------
# Vehicle SER parking exemption schemas
# (GET/POST/DELETE /vehicles/{id}/ser-parking-exemptions)
# ---------------------------------------------------------------------------


class VehicleSerParkingExemptionResponse(BaseModel):
    """A vehicle's stored SER parking exemption, or nulls if unset."""

    city_code: str | None
    zone_number: str | None


class SetVehicleSerParkingExemptionRequest(StrictRequestModel):
    """Request body for POST /vehicles/{id}/ser-parking-exemptions."""

    # Generously above the one seeded value ("madrid") — cities.code has no
    # DB-level cap, so this is a request-hygiene bound, not a DB-mirroring
    # one (see design.md decision 3).
    city_code: str = Field(..., max_length=50)
    # Matches vehicle_ser_parking_exemptions.zone_number's VARCHAR(10) column —
    # rejected here with a clean 422 instead of reaching Postgres as a
    # DataError (sibling of IntegrityError, not caught by the repository's
    # FK-violation handling).
    zone_number: str = Field(..., max_length=10)


# ---------------------------------------------------------------------------
# User preferences schemas (GET/PUT /preferences)
# ---------------------------------------------------------------------------


class UserPreferencesResponse(BaseModel):
    """Current user's preferences."""

    default_ticket_duration_minutes: int
    auto_create_ticket: bool
    preferred_notification_channel: str | None
    notification_language: str | None
    timezone: str | None


class UpdateUserPreferencesRequest(StrictRequestModel):
    """Full-resource replace payload for /preferences."""

    default_ticket_duration_minutes: int = Field(..., gt=0)
    auto_create_ticket: bool
    preferred_notification_channel: str | None
    notification_language: str | None
    timezone: str | None


# ---------------------------------------------------------------------------
# SER ticket provider connect schemas (discriminated union by provider)
# ---------------------------------------------------------------------------


class ConnectElParkingRequest(StrictRequestModel):
    """Connect-account payload for the ElParking SER ticket provider."""

    provider: Literal["elparking"]
    email: EmailStr = Field(..., min_length=6, max_length=100)
    password: str = Field(..., min_length=1, max_length=100)


# Only one variant exists today, but the discriminated-union shape (mirroring
# RegisterVehicleRequest) keeps the door open for a second provider later
# without changing the endpoint's request contract.
ConnectSerTicketProviderRequest = Annotated[
    ConnectElParkingRequest,
    Field(discriminator="provider"),
]


# ---------------------------------------------------------------------------
# SER ticket provider connection status / disconnect schemas
# ---------------------------------------------------------------------------


class SerTicketProviderConnectionsResponse(BaseModel):
    """Providers the current user has connected."""

    providers: list[str]


class DisconnectSerTicketProviderResponse(BaseModel):
    """Result of disconnecting a SER ticket provider connection."""

    logout_succeeded: bool


# ---------------------------------------------------------------------------
# Notification channel schemas
# ---------------------------------------------------------------------------


class TelegramLinkCodeResponse(BaseModel):
    """A Telegram deep link carrying a signed, time-limited linking token."""

    deep_link: str


class NotificationChannelsResponse(BaseModel):
    """Notification channels the current user has configured."""

    channels: list[str]


class NotificationLanguagesResponse(BaseModel):
    """The system's supported notification languages (SUPPORTED_LANGUAGES)."""

    languages: list[str]


# ---------------------------------------------------------------------------
# Notification type preference schemas (GET /notifications/types,
# GET/PUT /notifications/preferences)
# ---------------------------------------------------------------------------


class NotificationTypeResponse(BaseModel):
    """One row of the notification_types catalog."""

    key: str
    label: str
    config_schema: dict[str, Any]


class NotificationPreferenceResponse(BaseModel):
    """
    The current user's preference for one notification type.

    `config` is the effective config: any field the type's config_schema
    declares that the user hasn't explicitly set (e.g. threshold_m) is
    resolved via its fallback default before being returned here.
    """

    type_key: str
    enabled: bool
    config: dict[str, Any]


class UpdateNotificationPreferenceRequest(StrictRequestModel):
    """Request body for PUT /notifications/preferences/{type_key}."""

    enabled: bool
    config: dict[str, Any] = {}
