"""
Application use case: ListUserVehicles.

Fetches all vehicles for a user and enriches each with its latest known location.
"""

from dataclasses import dataclass
from uuid import UUID

from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.entities.vehicle_location import VehicleLocation
from mobility_manager.domain.ports.vehicle_location_repository import (
    VehicleLocationRepository,
)
from mobility_manager.domain.ports.vehicle_repository import VehicleRepository


@dataclass
class VehicleWithLocation:
    """Vehicle entity paired with its latest location (or None if not yet known)."""

    vehicle: Vehicle
    location: VehicleLocation | None


class ListUserVehicles:
    """
    List all vehicles belonging to a user, each enriched with its latest location.

    Performs an N+1 read for small personal datasets — acceptable by design (D1).
    """

    def __init__(
        self,
        vehicle_repo: VehicleRepository,
        location_repo: VehicleLocationRepository,
    ) -> None:
        self._vehicle_repo = vehicle_repo
        self._location_repo = location_repo

    def execute(self, user_id: UUID) -> list[VehicleWithLocation]:
        """
        Return all vehicles for the given user enriched with latest location.

        Args:
            user_id: UUID of the authenticated user.

        Returns:
            List of VehicleWithLocation ordered by vehicle creation (DB default).
        """
        vehicles = self._vehicle_repo.get_all_by_user_id(user_id)
        return [
            VehicleWithLocation(vehicle=v, location=self._location_repo.get_latest(v.id))
            for v in vehicles
        ]
