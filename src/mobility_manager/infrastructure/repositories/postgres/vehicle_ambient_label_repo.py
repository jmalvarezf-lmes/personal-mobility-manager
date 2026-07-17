"""
Infrastructure: PostgresVehicleAmbientLabelRepository.

Stores per-vehicle ambient label lookup state (1:1 with vehicles). Uses
INSERT ... ON CONFLICT DO UPDATE for upsert, mirroring
PostgresNotificationPreferencesRepository.update().
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from mobility_manager.domain.entities.vehicle_ambient_label import (
    VehicleAmbientLabel,
)
from mobility_manager.domain.ports.vehicle_ambient_label_repository import (
    VehicleAmbientLabelRepository,
)
from mobility_manager.domain.value_objects.ambient_label import AmbientLabel
from mobility_manager.domain.value_objects.ambient_label_status import (
    AmbientLabelStatus,
)
from mobility_manager.infrastructure.orm.tables import (
    vehicle_ambient_labels_table,
    vehicles_table,
)


class PostgresVehicleAmbientLabelRepository(VehicleAmbientLabelRepository):
    """PostgreSQL-backed ambient label repository using SQLAlchemy Core."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_by_vehicle_id(self, vehicle_id: UUID) -> VehicleAmbientLabel | None:
        """Return the ambient label row for the given vehicle, or None if never looked up."""
        with self._engine.connect() as conn:
            row = conn.execute(
                select(vehicle_ambient_labels_table).where(
                    vehicle_ambient_labels_table.c.vehicle_id == vehicle_id
                )
            ).fetchone()
        if row is None:
            return None
        return self._row_to_vehicle_ambient_label(row)

    def upsert(
        self,
        vehicle_id: UUID,
        label: AmbientLabel | None,
        status: AmbientLabelStatus,
        last_checked_at: datetime,
    ) -> None:
        """Insert or update the ambient label row for the given vehicle."""
        label_value = label.value if label is not None else None
        stmt = (
            insert(vehicle_ambient_labels_table)
            .values(
                vehicle_id=vehicle_id,
                label=label_value,
                status=status.value,
                last_checked_at=last_checked_at,
            )
            .on_conflict_do_update(
                index_elements=["vehicle_id"],
                set_={
                    "label": label_value,
                    "status": status.value,
                    "last_checked_at": last_checked_at,
                },
            )
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def get_vehicles_needing_lookup(self, cooldown: timedelta) -> list[UUID]:
        """
        Return IDs of vehicles with a plate and either no ambient label row,
        or a row with status != found whose last_checked_at is older than
        `cooldown`. Vehicles with status=found are permanently excluded.
        """
        cutoff = datetime.now(UTC) - cooldown
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(vehicles_table.c.id)
                .select_from(
                    vehicles_table.outerjoin(
                        vehicle_ambient_labels_table,
                        vehicles_table.c.id == vehicle_ambient_labels_table.c.vehicle_id,
                    )
                )
                .where(
                    vehicles_table.c.license_plate.is_not(None),
                    or_(
                        vehicle_ambient_labels_table.c.vehicle_id.is_(None),
                        and_(
                            vehicle_ambient_labels_table.c.status != AmbientLabelStatus.FOUND.value,
                            vehicle_ambient_labels_table.c.last_checked_at < cutoff,
                        ),
                    ),
                )
            ).fetchall()
        return [UUID(str(row.id)) for row in rows]

    @staticmethod
    def _row_to_vehicle_ambient_label(row: object) -> VehicleAmbientLabel:
        return VehicleAmbientLabel(
            vehicle_id=row.vehicle_id,  # type: ignore[attr-defined]
            label=AmbientLabel(row.label) if row.label is not None else None,  # type: ignore[attr-defined]
            status=AmbientLabelStatus(row.status),  # type: ignore[attr-defined]
            last_checked_at=row.last_checked_at,  # type: ignore[attr-defined]
        )
