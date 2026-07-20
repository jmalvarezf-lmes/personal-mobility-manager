"""
Infrastructure: PostgresVehicleLocationRepository.

Appends each location update as a new row; never overwrites.
get_latest returns the row with the highest recorded_at for the given vehicle.
get_previous returns the row immediately before a given received_at cutoff,
since by the time VehicleLocationUpdated fires the new row is already saved
and get_latest would just return it back. received_at (server receipt time)
is used rather than recorded_at (source GPS fix time) because some sources
report the same recorded_at across many consecutive polls (a stale/cached
fix) — comparing on recorded_at would then skip past the true previous row
and fall back to an older, possibly distant, one.
list_history pages through the full history, newest first (see
add-vehicle-location-history design.md).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.engine import Engine

from mobility_manager.domain.entities.vehicle_location import VehicleLocation
from mobility_manager.domain.ports.vehicle_location_repository import (
    VehicleLocationRepository,
)
from mobility_manager.infrastructure.orm.tables import vehicle_locations_table


class PostgresVehicleLocationRepository(VehicleLocationRepository):
    """PostgreSQL-backed vehicle location repository using SQLAlchemy Core."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def save(self, location: VehicleLocation) -> None:
        """Append a new location row."""
        with self._engine.begin() as conn:
            conn.execute(
                vehicle_locations_table.insert().values(
                    id=location.id,
                    vehicle_id=location.vehicle_id,
                    latitude=location.latitude,
                    longitude=location.longitude,
                    recorded_at=location.recorded_at,
                    received_at=location.received_at,
                    source=location.source,
                )
            )

    def get_latest(self, vehicle_id: UUID) -> VehicleLocation | None:
        """Return the most recent location for the given vehicle, or None."""
        with self._engine.connect() as conn:
            row = conn.execute(
                select(vehicle_locations_table)
                .where(vehicle_locations_table.c.vehicle_id == vehicle_id)
                .order_by(desc(vehicle_locations_table.c.recorded_at))
                .limit(1)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_location(row)

    def get_previous(self, vehicle_id: UUID, before: datetime) -> VehicleLocation | None:
        """Return the location received immediately before `before`, or None."""
        with self._engine.connect() as conn:
            row = conn.execute(
                select(vehicle_locations_table)
                .where(
                    vehicle_locations_table.c.vehicle_id == vehicle_id,
                    vehicle_locations_table.c.received_at < before,
                )
                .order_by(desc(vehicle_locations_table.c.received_at))
                .limit(1)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_location(row)

    def list_history(self, vehicle_id: UUID, limit: int, offset: int) -> tuple[list[VehicleLocation], bool]:
        """
        Return a page of `vehicle_id`'s location history, newest first.

        Fetches `limit + 1` rows so `has_more` can be derived from whether
        that extra row came back, avoiding a second COUNT(*) query (see
        add-vehicle-location-history design.md). The extra row, if present,
        is trimmed before returning.

        Ordered by `recorded_at DESC` with `received_at DESC` as a secondary
        key: duplicate `recorded_at` values are a real occurrence for this
        table (see module docstring / get_previous above), and without a
        tie-breaker, OFFSET/LIMIT pagination across separate page-load
        queries isn't guaranteed stable when a tie sits at a page boundary.
        """
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(vehicle_locations_table)
                .where(vehicle_locations_table.c.vehicle_id == vehicle_id)
                .order_by(
                    desc(vehicle_locations_table.c.recorded_at),
                    desc(vehicle_locations_table.c.received_at),
                )
                .offset(offset)
                .limit(limit + 1)
            ).fetchall()

        has_more = len(rows) > limit
        return [self._row_to_location(row) for row in rows[:limit]], has_more

    @staticmethod
    def _row_to_location(row: object) -> VehicleLocation:
        return VehicleLocation(
            id=row.id,  # type: ignore[attr-defined]
            vehicle_id=row.vehicle_id,  # type: ignore[attr-defined]
            latitude=row.latitude,  # type: ignore[attr-defined]
            longitude=row.longitude,  # type: ignore[attr-defined]
            recorded_at=row.recorded_at,  # type: ignore[attr-defined]
            received_at=row.received_at,  # type: ignore[attr-defined]
            source=row.source,  # type: ignore[attr-defined]
        )
