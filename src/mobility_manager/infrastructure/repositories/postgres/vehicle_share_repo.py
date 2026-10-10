"""
Infrastructure: PostgresVehicleShareRepository.

SQLAlchemy Core implementation of the VehicleShareRepository port.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from mobility_manager.domain.entities.vehicle_share import VehicleShare
from mobility_manager.domain.ports.vehicle_share_repository import (
    VehicleShareRepository,
)
from mobility_manager.infrastructure.orm.tables import vehicle_shares_table


class PostgresVehicleShareRepository(VehicleShareRepository):
    """PostgreSQL-backed vehicle share repository using SQLAlchemy Core."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def save(self, share: VehicleShare) -> None:
        """Insert a share grant idempotently."""
        stmt = (
            insert(vehicle_shares_table)
            .values(
                vehicle_id=share.vehicle_id,
                user_id=share.user_id,
                created_at=share.created_at,
            )
            .on_conflict_do_nothing(index_elements=["vehicle_id", "user_id"])
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def find_by_vehicle_and_user(self, vehicle_id: UUID, user_id: UUID) -> VehicleShare | None:
        """Return the share for the given vehicle and user, or None."""
        with self._engine.connect() as conn:
            row = conn.execute(
                select(vehicle_shares_table)
                .where(vehicle_shares_table.c.vehicle_id == vehicle_id)
                .where(vehicle_shares_table.c.user_id == user_id)
            ).fetchone()

        if row is None:
            return None
        return self._row_to_share(row)

    def list_sharees(self, vehicle_id: UUID) -> list[VehicleShare]:
        """Return all share grants for the given vehicle."""
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(vehicle_shares_table)
                .where(vehicle_shares_table.c.vehicle_id == vehicle_id)
                .order_by(vehicle_shares_table.c.created_at)
            ).fetchall()

        return [self._row_to_share(r) for r in rows]

    def delete(self, vehicle_id: UUID, user_id: UUID) -> None:
        """Delete the share for the given vehicle and user (idempotent)."""
        with self._engine.begin() as conn:
            conn.execute(
                vehicle_shares_table.delete()
                .where(vehicle_shares_table.c.vehicle_id == vehicle_id)
                .where(vehicle_shares_table.c.user_id == user_id)
            )

    def list_vehicle_ids_for_user(self, user_id: UUID) -> list[UUID]:
        """Return all vehicle ids shared with the given user."""
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(vehicle_shares_table.c.vehicle_id)
                .where(vehicle_shares_table.c.user_id == user_id)
            ).fetchall()

        return [r.vehicle_id for r in rows]

    @staticmethod
    def _row_to_share(row: object) -> VehicleShare:
        return VehicleShare(
            vehicle_id=row.vehicle_id,  # type: ignore[attr-defined]
            user_id=row.user_id,  # type: ignore[attr-defined]
            created_at=row.created_at,  # type: ignore[attr-defined]
        )
