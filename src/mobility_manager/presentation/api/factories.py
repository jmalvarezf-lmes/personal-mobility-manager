"""
Presentation: Factories for converting API request bodies into use-case input objects.

These factories live in the presentation layer so the application layer remains
free of any FastAPI / Pydantic dependencies (Clean Architecture boundary).
"""

from dataclasses import dataclass
from uuid import UUID

from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.domain.value_objects.ser_provider_credentials import (
    SerProviderCredentials,
)
from mobility_manager.domain.value_objects.toyota_config import ToyotaConfig
from mobility_manager.presentation.api.schemas import (
    BaseUpdateVehicleRequest,
    ConnectElParkingRequest,
    ConnectSerTicketProviderRequest,
    RegisterGenericRequest,
    RegisterToyotaRequest,
)


@dataclass
class RegisterVehicleInput:
    """Normalised input for the RegisterVehicle use case."""

    brand: Brand
    display_name: str
    vin: str | None
    toyota_config: ToyotaConfig | None
    license_plate: str | None = None


class VehicleRegisterFactory:
    """Build a RegisterVehicleInput from a validated request body."""

    @staticmethod
    def build(body: RegisterToyotaRequest | RegisterGenericRequest) -> RegisterVehicleInput:
        """Convert a registration request body into a use-case input object."""
        if isinstance(body, RegisterToyotaRequest):
            toyota_config = ToyotaConfig(
                username=body.username,
                password=body.password,
                locale=body.locale,
                vin=body.vin,
            )
            return RegisterVehicleInput(
                brand=body.brand,
                display_name=body.display_name,
                vin=body.vin,
                toyota_config=toyota_config,
                license_plate=body.license_plate,
            )
        # Generic
        return RegisterVehicleInput(
            brand=body.brand,
            display_name=body.display_name,
            vin=None,
            toyota_config=None,
            license_plate=body.license_plate,
        )


@dataclass
class VehicleUpdateInput:
    """Normalised input for the UpdateVehicle use case."""

    display_name: str
    license_plate: str | None
    username: str | None
    locale: str | None
    password: str | None


class VehicleUpdateFactory:
    """Build a VehicleUpdateInput from a validated request body."""

    @staticmethod
    def build(body: BaseUpdateVehicleRequest) -> VehicleUpdateInput:
        """Convert an update request body into a use-case input object."""
        from mobility_manager.presentation.api.schemas import UpdateToyotaRequest

        if isinstance(body, UpdateToyotaRequest):
            return VehicleUpdateInput(
                display_name=body.display_name,
                license_plate=body.license_plate,
                username=body.username,
                locale=body.locale,
                password=body.password,
            )
        # Generic and any future brand without brand-specific credentials
        return VehicleUpdateInput(
            display_name=body.display_name,
            license_plate=body.license_plate,
            username=None,
            locale=None,
            password=None,
        )


# ---------------------------------------------------------------------------
# SER ticket provider connect factory
# ---------------------------------------------------------------------------

# Identifies this backend as a server integration, not a spoofed device, when
# talking to providers (e.g. ElParking) that track a per-login "model" field.
_SER_PROVIDER_MODEL = "personal-mobility-manager-server"


class SerTicketProviderConnectFactory:
    """Build a SerProviderCredentials from a validated connect-request body."""

    @staticmethod
    def build(body: ConnectSerTicketProviderRequest, user_id: UUID) -> SerProviderCredentials:
        """
        Convert a connect-request body into provider-specific SerProviderCredentials.

        `uid`/`model` are injected here (presentation layer), not in the use
        case or the provider — ConnectSerTicketProvider stays provider-agnostic
        and never learns that "uid" is an ElParking concept.
        """
        if isinstance(body, ConnectElParkingRequest):
            return SerProviderCredentials(
                data={
                    "email": body.email,
                    "password": body.password,
                    "uid": str(user_id),
                    "model": _SER_PROVIDER_MODEL,
                }
            )
        raise ValueError(f"Unsupported SER ticket provider request type: {type(body)!r}")
