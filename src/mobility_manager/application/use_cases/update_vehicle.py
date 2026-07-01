"""
Application use case: UpdateVehicle.

Updates a vehicle's display_name and, for Toyota, optionally re-encrypts credentials.
"""

from uuid import UUID

from mobility_manager.domain.exceptions import VehicleNotFoundError
from mobility_manager.domain.ports.vehicle_config_repository import (
    VehicleConfigRepository,
)
from mobility_manager.domain.ports.vehicle_repository import VehicleRepository
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.domain.value_objects.toyota_config import ToyotaConfig


class UpdateVehicle:
    """
    Update a vehicle's display_name; re-encrypt Toyota credentials when a new password is provided (D3).
    """

    def __init__(
        self,
        vehicle_repo: VehicleRepository,
        config_repo: VehicleConfigRepository,
    ) -> None:
        self._vehicle_repo = vehicle_repo
        self._config_repo = config_repo

    def execute(
        self,
        vehicle_id: UUID,
        display_name: str,
        username: str | None = None,
        locale: str | None = None,
        password: str | None = None,
    ) -> None:
        """
        Update the vehicle.

        Args:
            vehicle_id: UUID of the vehicle to update.
            display_name: New human-readable name.
            username: Toyota account username (ignored for Generic).
            locale: Toyota locale string (ignored for Generic).
            password: New Toyota password. If None or empty string, skip re-encryption (D3).

        Raises:
            VehicleNotFoundError: If no vehicle exists with the given ID.
        """
        vehicle = self._vehicle_repo.get_by_id(vehicle_id)
        if vehicle is None:
            raise VehicleNotFoundError(f"Vehicle {vehicle_id} not found")

        self._vehicle_repo.update_display_name(vehicle_id, display_name)

        if vehicle.brand == Brand.TOYOTA and password:
            existing = self._config_repo.get_toyota_config(vehicle_id)
            updated = ToyotaConfig(
                username=username or existing.username,
                password=password,
                locale=locale or existing.locale,
                vin=existing.vin,
            )
            self._config_repo.update_toyota_config(vehicle_id, updated)
