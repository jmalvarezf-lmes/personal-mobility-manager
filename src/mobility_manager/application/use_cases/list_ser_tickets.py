"""
Application use case: ListSerTickets.

Returns a paginated page of a vehicle's SER tickets, newest first. Thin
wrapper over ParkingTicketRepository.list_by_vehicle — mirrors
ListVehicleLocationHistory in staying thin and not enforcing ownership
itself; ownership is enforced by the router's `require_owned_vehicle`
dependency before this use case ever runs (see add-ser-ticket-history-ui
design.md).
"""

from uuid import UUID

from mobility_manager.domain.entities.parking_ticket import ParkingTicket
from mobility_manager.domain.ports.parking_ticket_repository import (
    ParkingTicketRepository,
)


class ListSerTickets:
    """Return a page of a vehicle's SER tickets, newest first."""

    def __init__(self, ticket_repo: ParkingTicketRepository) -> None:
        self._ticket_repo = ticket_repo

    def execute(self, vehicle_id: UUID, limit: int, offset: int) -> tuple[list[ParkingTicket], bool]:
        """
        Fetch a page of SER tickets for the given vehicle.

        Args:
            vehicle_id: UUID of the vehicle to query.
            limit: Maximum number of rows to return.
            offset: Number of rows to skip before the page starts.

        Returns:
            A tuple of (items, has_more): items is the page of tickets
            (newest first, regardless of `auto_created`), has_more indicates
            whether further rows exist beyond this page. A vehicle with no
            tickets returns ([], False) rather than raising.
        """
        return self._ticket_repo.list_by_vehicle(vehicle_id, limit=limit, offset=offset)
