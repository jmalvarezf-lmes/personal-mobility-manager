"""
Infrastructure: PostgresVehicleRepository.

SQLAlchemy Core implementation of the VehicleRepository port.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import Engine

from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.ports.vehicle_repository import VehicleRepository
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.infrastructure.orm.tables import vehicles_table


class PostgresVehicleRepository(VehicleRepository):
    """PostgreSQL-backed vehicle repository using SQLAlchemy Core."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def save(self, vehicle: Vehicle) -> None:
        """Insert a new vehicle row."""
        with self._engine.begin() as conn:
            conn.execute(
                vehicles_table.insert().values(
                    id=vehicle.id,
                    brand=vehicle.brand.value,
                    display_name=vehicle.display_name,
                    vin=vehicle.vin,
                    created_at=vehicle.created_at,
                    user_id=vehicle.user_id,
                )
            )

    def get_by_id(self, vehicle_id: UUID) -> Vehicle | None:
        """Return the vehicle with the given UUID, or None."""
        with self._engine.connect() as conn:
            row = conn.execute(select(vehicles_table).where(vehicles_table.c.id == vehicle_id)).fetchone()
        if row is None:
            return None
        return self._row_to_vehicle(row)

    def find_by_id(self, vehicle_id: UUID) -> Vehicle | None:
        """Return the vehicle with the given UUID, or None (alias for ownership checks)."""
        return self.get_by_id(vehicle_id)

    def get_all_by_brand(self, brand: Brand) -> list[Vehicle]:
        """Return all vehicles for the given brand."""
        with self._engine.connect() as conn:
            rows = conn.execute(select(vehicles_table).where(vehicles_table.c.brand == brand.value)).fetchall()
        return [self._row_to_vehicle(r) for r in rows]

    def get_all_by_user_id(self, user_id: UUID) -> list[Vehicle]:
        """Return all vehicles owned by the given user."""
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(vehicles_table).where(vehicles_table.c.user_id == user_id)
            ).fetchall()
        return [self._row_to_vehicle(r) for r in rows]

    def delete(self, vehicle_id: UUID) -> None:
        """Delete the vehicle row; DB cascade removes child rows."""
        with self._engine.begin() as conn:
            conn.execute(vehicles_table.delete().where(vehicles_table.c.id == vehicle_id))

    def update_display_name(self, vehicle_id: UUID, display_name: str) -> None:
        """Update the display_name column for the given vehicle."""
        with self._engine.begin() as conn:
            conn.execute(
                vehicles_table.update()
                .where(vehicles_table.c.id == vehicle_id)
                .values(display_name=display_name)
            )

    @staticmethod
    def _row_to_vehicle(row: object) -> Vehicle:
        return Vehicle(
            id=row.id,  # type: ignore[attr-defined]
            brand=Brand(row.brand),  # type: ignore[attr-defined]
            display_name=row.display_name,  # type: ignore[attr-defined]
            vin=row.vin,  # type: ignore[attr-defined]
            created_at=row.created_at,  # type: ignore[attr-defined]
            user_id=row.user_id,  # type: ignore[attr-defined]
        )
