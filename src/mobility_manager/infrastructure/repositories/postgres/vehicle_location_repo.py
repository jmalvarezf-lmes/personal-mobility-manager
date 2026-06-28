"""
Infrastructure: PostgresVehicleLocationRepository.

Appends each location update as a new row; never overwrites.
get_latest returns the row with the highest recorded_at for the given vehicle.
"""

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
