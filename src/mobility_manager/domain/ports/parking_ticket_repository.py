"""
Port (interface): ParkingTicketRepository.

Abstract contract for ParkingTicket persistence.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from mobility_manager.domain.entities.parking_ticket import ParkingTicket


class ParkingTicketRepository(ABC):
    """Abstract repository for ParkingTicket entities."""

    @abstractmethod
    def save(self, ticket: ParkingTicket) -> None:
        """Persist a ParkingTicket."""
        ...

    @abstractmethod
    def find_all_active_for_vehicle(self, vehicle_id: UUID, at: datetime) -> list[ParkingTicket]:
        """
        Return every one of the vehicle's ParkingTicket rows whose `end_date`
        is still in the future relative to `at` — not just a single one — or
        an empty list if it has none.

        Renamed and widened from the original single-ticket
        `find_active_for_vehicle` (see change-ser-auto-ticket-zone-gate 4R
        review fix #1): a vehicle can legitimately hold more than one
        concurrently-active ticket, one per SER zone it has entered while a
        previous zone's ticket has not yet expired, so returning only the
        single row with the latest `end_date` could silently hide a still-
        active ticket for the zone actually being checked. This method
        remains vehicle-scoped only — it does not filter by zone itself.
        Callers that care about zone (see DetermineSerTicketRequirement's
        active-ticket short-circuit) must inspect each returned ticket's own
        `(city_code, zone_number)` to decide whether any of them covers the
        zone in question.
        """
        ...
