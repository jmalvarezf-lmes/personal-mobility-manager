"""
Application use case: ListVehicleLocationHistory.

Returns a paginated page of a vehicle's recorded location history, newest
first. Thin wrapper over VehicleLocationRepository.list_history — mirrors
GetLatestVehicleLocation in staying thin and not enforcing ownership itself;
ownership is enforced by the router's `require_owned_vehicle` dependency
before this use case ever runs (see add-vehicle-location-history design.md).
"""

from uuid import UUID

from mobility_manager.domain.entities.vehicle_location import VehicleLocation
from mobility_manager.domain.ports.vehicle_location_repository import (
    VehicleLocationRepository,
)


class ListVehicleLocationHistory:
    """Return a page of a vehicle's location history, newest first."""

    def __init__(self, location_repo: VehicleLocationRepository) -> None:
        self._location_repo = location_repo

    def execute(self, vehicle_id: UUID, limit: int, offset: int) -> tuple[list[VehicleLocation], bool]:
        """
        Fetch a page of location history for the given vehicle.

        Args:
            vehicle_id: UUID of the vehicle to query.
            limit: Maximum number of rows to return.
            offset: Number of rows to skip before the page starts.

        Returns:
            A tuple of (items, has_more): items is the page of locations
            (newest first), has_more indicates whether further rows exist
            beyond this page. A vehicle with no recorded locations returns
            ([], False) rather than raising.
        """
        return self._location_repo.list_history(vehicle_id, limit, offset)
