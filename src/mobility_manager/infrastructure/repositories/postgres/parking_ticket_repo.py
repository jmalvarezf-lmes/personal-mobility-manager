"""
Infrastructure: PostgresParkingTicketRepository.

Stores created ParkingTicket rows.
"""

from sqlalchemy.engine import Engine

from mobility_manager.domain.entities.parking_ticket import ParkingTicket
from mobility_manager.domain.ports.parking_ticket_repository import (
    ParkingTicketRepository,
)
from mobility_manager.infrastructure.orm.tables import parking_tickets_table


class PostgresParkingTicketRepository(ParkingTicketRepository):
    """PostgreSQL-backed ParkingTicket repository."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def save(self, ticket: ParkingTicket) -> None:
        """Persist a new ParkingTicket row."""
        with self._engine.begin() as conn:
            conn.execute(
                parking_tickets_table.insert().values(
                    id=ticket.id,
                    vehicle_id=ticket.vehicle_id,
                    user_id=ticket.user_id,
                    provider=ticket.provider,
                    duration_minutes=ticket.duration_minutes,
                    provider_reference=ticket.provider_reference,
                    cost=ticket.cost,
                    end_date=ticket.end_date,
                    created_at=ticket.created_at,
                )
            )
