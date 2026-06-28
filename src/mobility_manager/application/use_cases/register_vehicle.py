"""
Application use case: RegisterVehicle.

Creates a new vehicle and its brand-specific configuration:
- Toyota: encrypts credentials via VehicleConfigRepository
- Generic: generates a random location_token
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.exceptions import BrandNotEnabledError
from mobility_manager.domain.ports.vehicle_config_repository import (
    VehicleConfigRepository,
)
from mobility_manager.domain.ports.vehicle_repository import VehicleRepository
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.domain.value_objects.generic_config import GenericConfig
from mobility_manager.domain.value_objects.toyota_config import ToyotaConfig


@dataclass
class RegisterVehicleResult:
    """Outcome of a successful vehicle registration."""

    vehicle_id: UUID
    brand: Brand
    display_name: str
    vin: str | None
    location_token: str | None  # populated only for Generic brand


class RegisterVehicle:
    """
    Register a new vehicle and store its brand-specific configuration.

    Validates that the brand is in the enabled list before proceeding.
    """

    def __init__(
        self,
        vehicle_repo: VehicleRepository,
        config_repo: VehicleConfigRepository,
        enabled_brands: list[Brand],
    ) -> None:
        self._vehicle_repo = vehicle_repo
        self._config_repo = config_repo
        self._enabled_brands = enabled_brands

    def execute(
        self,
        brand: Brand,
        display_name: str,
        vin: str | None = None,
        toyota_config: ToyotaConfig | None = None,
    ) -> RegisterVehicleResult:
        """
        Register a vehicle.

        Args:
            brand: The vehicle brand (must be in enabled_brands).
            display_name: Human-readable name for the vehicle.
            vin: Vehicle Identification Number (required for Toyota).
            toyota_config: Decrypted Toyota credentials (required for Toyota brand).

        Returns:
            RegisterVehicleResult with vehicle_id and location_token (Generic only).

        Raises:
            BrandNotEnabledError: If the brand is not in the enabled list.
            ValueError: If Toyota brand is requested but toyota_config is not provided.
        """
        if brand not in self._enabled_brands:
            raise BrandNotEnabledError(
                f"Brand {brand.value!r} is not enabled. "
                f"Enabled brands: {[b.value for b in self._enabled_brands]}"
            )

        vehicle = Vehicle(
            id=uuid4(),
            brand=brand,
            display_name=display_name,
            vin=vin,
            created_at=datetime.now(timezone.utc),
        )
        self._vehicle_repo.save(vehicle)

        location_token: str | None = None

        if brand == Brand.TOYOTA:
            if toyota_config is None:
                raise ValueError("toyota_config is required for Toyota brand registration")
            self._config_repo.save_toyota_config(vehicle.id, toyota_config)

        elif brand == Brand.GENERIC:
            location_token = str(uuid4())
            self._config_repo.save_generic_config(
                vehicle.id, GenericConfig(location_token=location_token)
            )

        return RegisterVehicleResult(
            vehicle_id=vehicle.id,
            brand=vehicle.brand,
            display_name=vehicle.display_name,
            vin=vehicle.vin,
            location_token=location_token,
        )
