"""
Port (interface): VehicleLocationRepository.

Abstract contract for vehicle location history persistence.
"""

from abc import ABC, abstractmethod
from datetime import datetime
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

    @abstractmethod
    def get_previous(self, vehicle_id: UUID, before: datetime) -> VehicleLocation | None:
        """
        Return the location recorded immediately before `before`, for the given vehicle.

        Returns the row with the greatest recorded_at strictly less than
        `before`, or None if no such row exists (e.g. `before` is the
        vehicle's first-ever recorded location). Needed because
        VehicleLocationUpdated fires after the new row is already saved, so
        get_latest can't be used to find the prior point (see design.md
        decision 1).
        """
        ...
