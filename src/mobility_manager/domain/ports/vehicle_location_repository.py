"""
Port (interface): VehicleLocationRepository.

Abstract contract for vehicle location history persistence.
"""
from abc import ABC, abstractmethod
from uuid import UUID

from mobility_manager.domain.entities.vehicle_location import VehicleLocation


class VehicleLocationRepository(ABC):
    """Abstract repository for vehicle location history."""

    @abstractmethod
    def save(self, location: VehicleLocation) -> None:
        """Append a new location row (full history is retained)."""
        ...

    @abstractmethod
    def get_latest(self, vehicle_id: UUID) -> VehicleLocation | None:
        """
        Return the most recent location for the given vehicle.

        Returns None if no location rows exist for this vehicle.
        The latest is determined by the highest recorded_at value.
        """
        ...
