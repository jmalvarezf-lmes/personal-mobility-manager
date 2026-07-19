"""
Infrastructure: PostgresVehicleSerParkingExemptionRepository.

Stores per-vehicle SER parking exemptions (1:1 with vehicles). Uses
INSERT ... ON CONFLICT DO UPDATE for upsert, mirroring
PostgresVehicleAmbientLabelRepository.upsert(). Only a violation of the
named composite FK on (city_code, zone_number) is translated to
InvalidSerParkingExemptionZoneError so the presentation layer can map it to
a 422 — discriminated by constraint name so the table's other (unnamed)
vehicle_id -> vehicles.id FK violation isn't mislabeled as an invalid zone.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from mobility_manager.domain.entities.vehicle_ser_parking_exemption import (
    VehicleSerParkingExemption,
)
from mobility_manager.domain.exceptions import InvalidSerParkingExemptionZoneError
from mobility_manager.domain.ports.vehicle_ser_parking_exemption_repository import (
    VehicleSerParkingExemptionRepository,
)
from mobility_manager.infrastructure.orm.tables import (
    vehicle_ser_parking_exemptions_table,
)

# Must match the composite FK's explicit `name=` in the create-table migration.
# Only a violation of this specific constraint means "invalid zone" — the
# table also has an unnamed vehicle_id -> vehicles.id FK, whose violation
# (e.g. the vehicle was deleted between the router's ownership check and
# this upsert) must not be mislabeled as an invalid zone.
_ZONE_AREA_FK_CONSTRAINT = "fk_vehicle_ser_parking_exemptions_zone_area"


class PostgresVehicleSerParkingExemptionRepository(VehicleSerParkingExemptionRepository):
    """PostgreSQL-backed vehicle SER parking exemption repository using SQLAlchemy Core."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def find_by_vehicle_id(self, vehicle_id: UUID) -> VehicleSerParkingExemption | None:
        """Return the exemption row for the given vehicle, or None if unset."""
        with self._engine.connect() as conn:
            row = conn.execute(
                select(vehicle_ser_parking_exemptions_table).where(
                    vehicle_ser_parking_exemptions_table.c.vehicle_id == vehicle_id
                )
            ).fetchone()
        if row is None:
            return None
        return self._row_to_entity(row)

    def upsert(self, vehicle_id: UUID, city_code: str, zone_number: str) -> VehicleSerParkingExemption:
        """
        Insert or replace the exemption row for the given vehicle.

        Raises:
            InvalidSerParkingExemptionZoneError: If (city_code, zone_number)
                has no matching ser_zone_areas row.
        """
        now = datetime.now(UTC)
        stmt = (
            insert(vehicle_ser_parking_exemptions_table)
            .values(
                vehicle_id=vehicle_id,
                city_code=city_code,
                zone_number=zone_number,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["vehicle_id"],
                set_={
                    "city_code": city_code,
                    "zone_number": zone_number,
                    "updated_at": now,
                },
            )
        )
        try:
            with self._engine.begin() as conn:
                conn.execute(stmt)
        except IntegrityError as exc:
            constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            if constraint_name != _ZONE_AREA_FK_CONSTRAINT:
                raise
            raise InvalidSerParkingExemptionZoneError(
                f"No ser_zone_areas row for (city_code={city_code!r}, zone_number={zone_number!r})"
            ) from exc

        return VehicleSerParkingExemption(
            vehicle_id=vehicle_id,
            city_code=city_code,
            zone_number=zone_number,
            updated_at=now,
        )

    def delete(self, vehicle_id: UUID) -> None:
        """Delete the exemption row for the given vehicle, if any (idempotent)."""
        with self._engine.begin() as conn:
            conn.execute(
                sa_delete(vehicle_ser_parking_exemptions_table).where(
                    vehicle_ser_parking_exemptions_table.c.vehicle_id == vehicle_id
                )
            )

    @staticmethod
    def _row_to_entity(row: object) -> VehicleSerParkingExemption:
        return VehicleSerParkingExemption(
            vehicle_id=row.vehicle_id,  # type: ignore[attr-defined]
            city_code=row.city_code,  # type: ignore[attr-defined]
            zone_number=row.zone_number,  # type: ignore[attr-defined]
            updated_at=row.updated_at,  # type: ignore[attr-defined]
        )
