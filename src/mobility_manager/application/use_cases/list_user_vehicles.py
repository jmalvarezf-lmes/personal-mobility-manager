"""
Application use case: ListUserVehicles.

Fetches all vehicles for a user and enriches each with its latest known location.
"""

from dataclasses import dataclass
from uuid import UUID

from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.entities.vehicle_location import VehicleLocation
from mobility_manager.domain.ports.parking_ticket_repository import (
    ParkingTicketRepository,
)
from mobility_manager.domain.ports.vehicle_location_repository import (
    VehicleLocationRepository,
)
from mobility_manager.domain.ports.vehicle_repository import VehicleRepository


@dataclass
class VehicleWithLocation:
    """Vehicle entity paired with its latest location (or None if not yet known)."""

    vehicle: Vehicle
    location: VehicleLocation | None
    # True if the vehicle has at least one ParkingTicket row, regardless of
    # `auto_created` — gates the "View SER tickets" button (see
    # add-ser-ticket-history-ui design.md D6).
    has_ser_tickets: bool = False


class ListUserVehicles:
    """
    List all vehicles belonging to a user, each enriched with its latest location.

    Performs an N+1 read for small personal datasets — acceptable by design (D1).
    """

    def __init__(
        self,
        vehicle_repo: VehicleRepository,
        location_repo: VehicleLocationRepository,
        ticket_repo: ParkingTicketRepository,
    ) -> None:
        self._vehicle_repo = vehicle_repo
        self._location_repo = location_repo
        self._ticket_repo = ticket_repo

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
            VehicleWithLocation(
                vehicle=v,
                location=self._location_repo.get_latest(v.id),
                has_ser_tickets=self._ticket_repo.has_any_for_vehicle(v.id),
            )
            for v in vehicles
        ]
