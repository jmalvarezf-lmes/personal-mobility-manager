"""
Application use case: GetLatestVehicleLocation.

Returns the most recent known GPS location for a vehicle.
Raises VehicleLocationNotFoundError if no location history exists.
"""

from uuid import UUID

from mobility_manager.domain.entities.vehicle_location import VehicleLocation
from mobility_manager.domain.exceptions import VehicleLocationNotFoundError
from mobility_manager.domain.ports.vehicle_location_repository import (
    VehicleLocationRepository,
)


class GetLatestVehicleLocation:
    """Return the most recent known location for a vehicle."""

    def __init__(self, location_repo: VehicleLocationRepository) -> None:
        self._location_repo = location_repo

    def execute(self, vehicle_id: UUID) -> VehicleLocation:
        """
        Fetch the latest location for the given vehicle.

        Args:
            vehicle_id: UUID of the vehicle to query.

        Returns:
            The VehicleLocation with the most recent recorded_at.

        Raises:
            VehicleLocationNotFoundError: If no location rows exist for this vehicle.
        """
        location = self._location_repo.get_latest(vehicle_id)
        if location is None:
            raise VehicleLocationNotFoundError(f"No location history found for vehicle {vehicle_id}")
        return location
