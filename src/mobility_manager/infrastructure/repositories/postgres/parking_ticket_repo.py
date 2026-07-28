"""
Infrastructure: PostgresParkingTicketRepository.

Stores created ParkingTicket rows.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, exists, select
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
                    latitude=ticket.latitude,
                    longitude=ticket.longitude,
                    auto_created=ticket.auto_created,
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

        return [self._row_to_ticket(row) for row in rows]

    def list_by_vehicle(self, vehicle_id: UUID, limit: int, offset: int) -> tuple[list[ParkingTicket], bool]:
        """
        Return a page of `vehicle_id`'s tickets, newest first.

        Fetches `limit + 1` rows so `has_more` can be derived from whether
        that extra row came back, avoiding a second COUNT(*) query — same
        technique as `PostgresVehicleLocationRepository.list_history`. No
        `auto_created` filter — every ticket for the vehicle is returned.

        Ordered by `created_at DESC` with `id ASC` as a secondary tiebreaker:
        without it, OFFSET/LIMIT pagination across separate page-load queries
        isn't guaranteed stable when two tickets share the same `created_at`
        and sit at a page boundary (same rationale as
        `PostgresVehicleLocationRepository.list_history`'s `received_at`
        tiebreaker).
        """
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(parking_tickets_table)
                .where(parking_tickets_table.c.vehicle_id == vehicle_id)
                .order_by(
                    desc(parking_tickets_table.c.created_at),
                    parking_tickets_table.c.id,
                )
                .offset(offset)
                .limit(limit + 1)
            ).fetchall()

        has_more = len(rows) > limit
        return [self._row_to_ticket(row) for row in rows[:limit]], has_more

    def has_any_for_vehicle(self, vehicle_id: UUID) -> bool:
        """Cheap existence check — not a full row fetch — regardless of `auto_created`."""
        with self._engine.connect() as conn:
            result = conn.execute(
                select(
                    exists().where(parking_tickets_table.c.vehicle_id == vehicle_id)
                )
            ).scalar()
        return bool(result)

    @staticmethod
    def _row_to_ticket(row: object) -> ParkingTicket:
        return ParkingTicket(
            id=row.id,  # type: ignore[attr-defined]
            vehicle_id=row.vehicle_id,  # type: ignore[attr-defined]
            user_id=row.user_id,  # type: ignore[attr-defined]
            provider=row.provider,  # type: ignore[attr-defined]
            duration_minutes=row.duration_minutes,  # type: ignore[attr-defined]
            provider_reference=row.provider_reference,  # type: ignore[attr-defined]
            cost=float(row.cost),  # type: ignore[attr-defined]
            end_date=row.end_date,  # type: ignore[attr-defined]
            created_at=row.created_at,  # type: ignore[attr-defined]
            city_code=row.city_code,  # type: ignore[attr-defined]
            zone_number=row.zone_number,  # type: ignore[attr-defined]
            latitude=row.latitude,  # type: ignore[attr-defined]
            longitude=row.longitude,  # type: ignore[attr-defined]
            auto_created=row.auto_created,  # type: ignore[attr-defined]
        )
