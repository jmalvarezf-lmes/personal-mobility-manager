"""create-vehicle-ser-parking-exemptions

Revision ID: x1y2z3a4b5c6
Revises: w0x1y2z3a4b5
Create Date: 2026-07-19 00:00:00.000000

Additive-only migration: adds `vehicle_ser_parking_exemptions`, at most one
row per vehicle, recording the (city_code, zone_number) SER zone the owner
has already paid to park in. `vehicle_id` is both the primary key and the
FK to vehicles.id (ON DELETE CASCADE) — see design.md D3. The composite FK
to ser_zone_areas(city_code, zone_number) guarantees only a zone with a
resolvable neighbourhood label (and thus a displayable picker option) can
be selected — see design.md D1/D2. No changes to any existing table.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "x1y2z3a4b5c6"
down_revision: str | Sequence[str] | None = "w0x1y2z3a4b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vehicle_ser_parking_exemptions",
        sa.Column(
            "vehicle_id",
            sa.Uuid(),
            sa.ForeignKey("vehicles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("city_code", sa.Text(), nullable=False),
        sa.Column("zone_number", sa.String(10), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["city_code", "zone_number"],
            ["ser_zone_areas.city_code", "ser_zone_areas.zone_number"],
            name="fk_vehicle_ser_parking_exemptions_zone_area",
        ),
    )


def downgrade() -> None:
    op.drop_table("vehicle_ser_parking_exemptions")
