"""
Presentation: Pydantic schemas for the FastAPI API layer.
"""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from mobility_manager.domain.value_objects.brand import Brand


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


# ---------------------------------------------------------------------------
# Vehicle registration schemas (discriminated union by brand)
# ---------------------------------------------------------------------------


class BaseRegisterVehicleRequest(BaseModel):
    """Common fields for all vehicle registration requests."""

    display_name: str
    license_plate: str | None = Field(None, max_length=20)


class RegisterToyotaRequest(BaseRegisterVehicleRequest):
    """Registration payload for a Toyota vehicle."""

    brand: Literal[Brand.TOYOTA]
    vin: str
    username: str
    password: str
    locale: str


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


# ---------------------------------------------------------------------------
# Location schemas
# ---------------------------------------------------------------------------


class PushLocationRequest(BaseModel):
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


# ---------------------------------------------------------------------------
# Vehicle update schemas (PUT /vehicles/{id})
# ---------------------------------------------------------------------------


class BaseUpdateVehicleRequest(BaseModel):
    """Common fields for all vehicle update requests."""

    display_name: str
    license_plate: str | None = Field(None, max_length=20)


class UpdateToyotaRequest(BaseUpdateVehicleRequest):
    """Update payload for a Toyota vehicle."""

    brand: Literal[Brand.TOYOTA]
    username: str
    locale: str
    password: str | None = None


class UpdateGenericRequest(BaseUpdateVehicleRequest):
    """Update payload for a generic vehicle."""

    brand: Literal[Brand.GENERIC]


UpdateVehicleRequest = Annotated[
    UpdateToyotaRequest | UpdateGenericRequest,
    Field(discriminator="brand"),
]


# ---------------------------------------------------------------------------
# User preferences schemas (GET/PUT /preferences)
# ---------------------------------------------------------------------------


class UserPreferencesResponse(BaseModel):
    """Current user's preferences."""

    default_ticket_duration_minutes: int
    auto_create_ticket: bool
    preferred_notification_channel: str | None
    notification_language: str | None


class UpdateUserPreferencesRequest(BaseModel):
    """Full-resource replace payload for /preferences."""

    default_ticket_duration_minutes: int = Field(..., gt=0)
    auto_create_ticket: bool
    preferred_notification_channel: str | None
    notification_language: str | None


# ---------------------------------------------------------------------------
# SER ticket provider connect schemas (discriminated union by provider)
# ---------------------------------------------------------------------------


class ConnectElParkingRequest(BaseModel):
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
