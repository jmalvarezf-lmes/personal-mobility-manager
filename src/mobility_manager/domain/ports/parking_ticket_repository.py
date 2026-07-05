"""
Port (interface): ParkingTicketRepository.

Abstract contract for ParkingTicket persistence.
"""

from abc import ABC, abstractmethod

from mobility_manager.domain.entities.parking_ticket import ParkingTicket


class ParkingTicketRepository(ABC):
    """Abstract repository for ParkingTicket entities."""

    @abstractmethod
    def save(self, ticket: ParkingTicket) -> None:
        """Persist a ParkingTicket."""
        ...
