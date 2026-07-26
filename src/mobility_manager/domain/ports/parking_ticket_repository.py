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
    def find_active_for_vehicle(self, vehicle_id: UUID, at: datetime) -> ParkingTicket | None:
        """
        Return the vehicle's most recent ParkingTicket whose `end_date` is
        still in the future relative to `at`, or None if it has no such
        ticket.

        Deliberately vehicle-scoped, not zone-scoped: ParkingTicket has no
        stored zone number today (see DetermineSerTicketRequirement's
        idempotency short-circuit, which uses this to avoid creating a
        duplicate real ticket for a vehicle that already has one active,
        regardless of which zone it was created for).
        """
        ...
