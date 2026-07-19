"""add-cascade-delete-to-ser-parking-exemption-zone-fk

Revision ID: y2z3a4b5c6d7
Revises: x1y2z3a4b5c6
Create Date: 2026-07-19 00:00:00.000000

Adds `ondelete="CASCADE"` to `vehicle_ser_parking_exemptions`' composite FK
on (city_code, zone_number) -> ser_zone_areas(city_code, zone_number).

Without this, the scheduled SER zone ingestion job crashed for any city
with at least one saved vehicle exemption: `bulk_replace()` used to delete
every existing `ser_zone_areas` row for the ingesting city before
re-inserting fresh ones, which violated this FK (no `ON DELETE` action)
the moment any vehicle referenced a still-live zone_number.

This migration is safe only paired with the accompanying fix to
`PostgresSerZoneRepository.bulk_replace()`, which now upserts (rather than
delete-then-reinserts) `ser_zone_areas` rows whose `zone_number` is still
present in a fresh ingestion run. With that fix in place, this CASCADE only
ever fires for a `zone_number` that has genuinely disappeared from a city's
re-ingested data (e.g. a retired SER zone) — at that point any exemption
still pointing at it is meaningless, so cascading it away is correct. See
add-vehicle-ser-parking-exemption design.md and tasks.md 11.4.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "y2z3a4b5c6d7"
down_revision: str | Sequence[str] | None = "x1y2z3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FK_NAME = "fk_vehicle_ser_parking_exemptions_zone_area"
_TABLE = "vehicle_ser_parking_exemptions"
_REFERENT = "ser_zone_areas"
_COLUMNS = ["city_code", "zone_number"]


def upgrade() -> None:
    op.drop_constraint(_FK_NAME, _TABLE, type_="foreignkey")
    op.create_foreign_key(
        _FK_NAME,
        _TABLE,
        _REFERENT,
        _COLUMNS,
        _COLUMNS,
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(_FK_NAME, _TABLE, type_="foreignkey")
    op.create_foreign_key(
        _FK_NAME,
        _TABLE,
        _REFERENT,
        _COLUMNS,
        _COLUMNS,
    )
