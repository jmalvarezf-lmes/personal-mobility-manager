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

    @abstractmethod
    def list_by_vehicle(self, vehicle_id: UUID, limit: int, offset: int) -> tuple[list[ParkingTicket], bool]:
        """
        Return a page of `vehicle_id`'s ParkingTicket rows, newest first.

        Returns up to `limit` rows starting at `offset`, ordered by
        `created_at` descending, regardless of `auto_created` — every ticket
        for the vehicle is included, not just auto-created ones. Paired with
        a boolean indicating whether further rows exist beyond this page,
        mirroring `VehicleLocationRepository.list_history` (see
        add-ser-ticket-history-ui design.md D4). Does not alter `save`'s
        existing behavior.
        """
        ...

    @abstractmethod
    def has_any_for_vehicle(self, vehicle_id: UUID) -> bool:
        """
        Return whether at least one ParkingTicket row exists for `vehicle_id`,
        regardless of `auto_created`.

        Implemented as a cheap existence check (not a full row fetch), so
        `GET /vehicles` can gate its `has_ser_tickets` field without an
        N+1 full-ticket-fetch cost per vehicle (see
        add-ser-ticket-history-ui design.md D6).
        """
        ...
