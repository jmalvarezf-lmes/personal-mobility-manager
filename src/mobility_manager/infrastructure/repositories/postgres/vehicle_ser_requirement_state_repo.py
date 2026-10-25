"""
Infrastructure: PostgresVehicleSerRequirementStateRepository.

SQLAlchemy Core implementation of VehicleSerRequirementStateRepository.
Stores one row per vehicle; upserts on save.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from mobility_manager.domain.entities.vehicle_ser_requirement_state import (
    VehicleSerRequirementState,
)
from mobility_manager.domain.ports.vehicle_ser_requirement_state_repository import (
    VehicleSerRequirementStateRepository,
)
from mobility_manager.infrastructure.orm.tables import (
    vehicle_ser_requirement_states_table,
)


class PostgresVehicleSerRequirementStateRepository(VehicleSerRequirementStateRepository):
    """PostgreSQL-backed vehicle SER requirement state repository using SQLAlchemy Core."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def find_by_vehicle_id(self, vehicle_id: UUID) -> VehicleSerRequirementState | None:
        """Return the current requirement state for the vehicle, or None."""
        with self._engine.connect() as conn:
            row = conn.execute(
                select(vehicle_ser_requirement_states_table)
                .where(vehicle_ser_requirement_states_table.c.vehicle_id == vehicle_id)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_state(row)

    def save(self, state: VehicleSerRequirementState) -> None:
        """Persist the requirement state, inserting or updating as needed."""
        values = {
            "vehicle_id": state.vehicle_id,
            "city_code": state.city_code,
            "zone_number": state.zone_number,
            "is_required": state.is_required,
            "activated_at": state.activated_at,
            "last_evaluated_at": state.last_evaluated_at,
        }
        with self._engine.begin() as conn:
            conn.execute(
                insert(vehicle_ser_requirement_states_table)
                .values(values)
                .on_conflict_do_update(
                    index_elements=["vehicle_id"],
                    set_=values,
                )
            )

    @staticmethod
    def _row_to_state(row: object) -> VehicleSerRequirementState:
        return VehicleSerRequirementState(
            vehicle_id=row.vehicle_id,  # type: ignore[attr-defined]
            city_code=row.city_code,  # type: ignore[attr-defined]
            zone_number=row.zone_number,  # type: ignore[attr-defined]
            is_required=row.is_required,  # type: ignore[attr-defined]
            activated_at=row.activated_at,  # type: ignore[attr-defined]
            last_evaluated_at=row.last_evaluated_at,  # type: ignore[attr-defined]
        )
