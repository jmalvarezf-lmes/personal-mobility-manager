"""
Presentation: Pydantic schemas for the FastAPI API layer.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from mobility_manager.domain.value_objects.brand import Brand


class SerZoneResponse(BaseModel):
    street_name: str
    zone_type: str
    spot_count: int
    distance_meters: int
    latitude: float
    longitude: float


class ConfigResponse(BaseModel):
    osm_tile_url: str | None


class SerZoneMapItem(BaseModel):
    street_name: str
    zone_type: str
    colour: str
    spot_count: int
    lat: float
    lng: float


class ListSerZonesResponse(BaseModel):
    city: str
    zones: list[SerZoneMapItem]


# ---------------------------------------------------------------------------
# Vehicle registration schemas (discriminated union by brand)
# ---------------------------------------------------------------------------


class RegisterToyotaRequest(BaseModel):
    """Registration payload for a Toyota vehicle."""

    brand: Literal[Brand.TOYOTA]
    display_name: str
    vin: str
    username: str
    password: str
    locale: str


class RegisterGenericRequest(BaseModel):
    """Registration payload for a generic (push-only) vehicle."""

    brand: Literal[Brand.GENERIC]
    display_name: str


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
    config: ToyotaConfigResponse | GenericConfigResponse


# ---------------------------------------------------------------------------
# Vehicle update schemas (PUT /vehicles/{id})
# ---------------------------------------------------------------------------


class UpdateToyotaRequest(BaseModel):
    """Update payload for a Toyota vehicle."""

    brand: Literal[Brand.TOYOTA]
    display_name: str
    username: str
    locale: str
    password: str | None = None


class UpdateGenericRequest(BaseModel):
    """Update payload for a generic vehicle."""

    brand: Literal[Brand.GENERIC]
    display_name: str


UpdateVehicleRequest = Annotated[
    UpdateToyotaRequest | UpdateGenericRequest,
    Field(discriminator="brand"),
]
