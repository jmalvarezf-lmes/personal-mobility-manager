"""add-city-code-to-ser-zone-tables

Revision ID: w0x1y2z3a4b5
Revises: v9w0x1y2z3a4
Create Date: 2026-07-18 00:00:00.000000

Adds `city_code` (FK to cities.code) to ser_zones, ser_zone_streets, and
ser_zone_areas, backfilling every existing row to 'madrid' via
server_default (same add-column-with-default pattern as
c1f3a8e72b04_add_zone_type_spot_count_drop_zone_code_label.py — Postgres
populates existing rows from the server_default at ALTER TABLE time, so no
separate UPDATE statement is needed). Also widens the keys that assumed
zone_number was globally unique:
  - ser_zones: UNIQUE(zone_number, zone_type) -> UNIQUE(city_code, zone_number, zone_type)
  - ser_zone_areas: PK(zone_number) -> PK(city_code, zone_number)
  - ser_zone_streets: INDEX(zone_number, zone_type) -> INDEX(city_code, zone_number, zone_type)

See design.md D5/D6 and the Migration Plan's downgrade note: this
downgrade is only safe as long as no second city has been onboarded since
upgrade — narrowing ser_zone_areas' PK back to a bare zone_number will raise
on duplicate zone_number values across cities, which is intentional, not a
bug.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "w0x1y2z3a4b5"
down_revision: str | Sequence[str] | None = "v9w0x1y2z3a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ser_zones",
        sa.Column("city_code", sa.Text(), sa.ForeignKey("cities.code"), nullable=False, server_default="madrid"),
    )
    op.add_column(
        "ser_zone_streets",
        sa.Column("city_code", sa.Text(), sa.ForeignKey("cities.code"), nullable=False, server_default="madrid"),
    )
    op.add_column(
        "ser_zone_areas",
        sa.Column("city_code", sa.Text(), sa.ForeignKey("cities.code"), nullable=False, server_default="madrid"),
    )

    op.drop_constraint("uq_ser_zones_zone_number_zone_type", "ser_zones", type_="unique")
    op.create_unique_constraint(
        "uq_ser_zones_city_zone_number_zone_type",
        "ser_zones",
        ["city_code", "zone_number", "zone_type"],
    )

    op.drop_index("idx_ser_zone_streets_zone", table_name="ser_zone_streets")
    op.create_index(
        "idx_ser_zone_streets_zone",
        "ser_zone_streets",
        ["city_code", "zone_number", "zone_type"],
    )

    op.drop_constraint("ser_zone_areas_pkey", "ser_zone_areas", type_="primary")
    op.create_primary_key(
        "ser_zone_areas_pkey",
        "ser_zone_areas",
        ["city_code", "zone_number"],
    )


def downgrade() -> None:
    op.drop_constraint("ser_zone_areas_pkey", "ser_zone_areas", type_="primary")
    op.create_primary_key("ser_zone_areas_pkey", "ser_zone_areas", ["zone_number"])

    op.drop_index("idx_ser_zone_streets_zone", table_name="ser_zone_streets")
    op.create_index("idx_ser_zone_streets_zone", "ser_zone_streets", ["zone_number", "zone_type"])

    op.drop_constraint("uq_ser_zones_city_zone_number_zone_type", "ser_zones", type_="unique")
    op.create_unique_constraint("uq_ser_zones_zone_number_zone_type", "ser_zones", ["zone_number", "zone_type"])

    op.drop_column("ser_zone_areas", "city_code")
    op.drop_column("ser_zone_streets", "city_code")
    op.drop_column("ser_zones", "city_code")
