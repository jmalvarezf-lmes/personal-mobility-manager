"""
Port (interface): VehicleRepository.

Abstract contract for vehicle entity persistence.
"""
from abc import ABC, abstractmethod
from uuid import UUID

from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.value_objects.brand import Brand


class VehicleRepository(ABC):
    """Abstract repository for vehicle entities."""

    @abstractmethod
    def save(self, vehicle: Vehicle) -> None:
        """Persist a new vehicle."""
        ...

    @abstractmethod
    def get_by_id(self, vehicle_id: UUID) -> Vehicle | None:
        """Return the vehicle with the given ID, or None if not found."""
        ...

    @abstractmethod
    def get_all_by_brand(self, brand: Brand) -> list[Vehicle]:
        """Return all vehicles with the given brand."""
        ...
