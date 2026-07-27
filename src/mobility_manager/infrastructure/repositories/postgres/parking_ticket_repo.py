"""
Infrastructure: PostgresParkingTicketRepository.

Stores created ParkingTicket rows.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
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
                    city_code=ticket.city_code,
                    zone_number=ticket.zone_number,
                )
            )

    def find_all_active_for_vehicle(self, vehicle_id: UUID, at: datetime) -> list[ParkingTicket]:
        """Return every one of the vehicle's ParkingTicket rows still active at `at`."""
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(parking_tickets_table).where(
                    parking_tickets_table.c.vehicle_id == vehicle_id,
                    parking_tickets_table.c.end_date > at,
                )
            ).fetchall()

        return [
            ParkingTicket(
                id=row.id,
                vehicle_id=row.vehicle_id,
                user_id=row.user_id,
                provider=row.provider,
                duration_minutes=row.duration_minutes,
                provider_reference=row.provider_reference,
                cost=float(row.cost),
                end_date=row.end_date,
                created_at=row.created_at,
                city_code=row.city_code,
                zone_number=row.zone_number,
            )
            for row in rows
        ]
