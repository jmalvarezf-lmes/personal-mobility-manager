"""add-ser-zone-boundaries

Revision ID: n1o2p3q4r5s6
Revises: m0n1o2p3q4r5
Create Date: 2026-07-11 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "n1o2p3q4r5s6"
down_revision: str | Sequence[str] | None = "m0n1o2p3q4r5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop point-based columns; ser_zones becomes zone-boundary shaped.
    op.drop_index("idx_ser_zones_coords", table_name="ser_zones")
    op.drop_column("ser_zones", "street_name")
    op.drop_column("ser_zones", "latitude")
    op.drop_column("ser_zones", "longitude")
    op.drop_column("ser_zones", "utm_x")
    op.drop_column("ser_zones", "utm_y")

    op.add_column(
        "ser_zones",
        sa.Column("zone_number", sa.String(10), nullable=False, server_default=""),
    )
    op.add_column(
        "ser_zones",
        sa.Column("district", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "ser_zones",
        sa.Column("geometry_wkt", sa.Text(), nullable=False, server_default=""),
    )
    op.create_unique_constraint(
        "uq_ser_zones_zone_number_zone_type",
        "ser_zones",
        ["zone_number", "zone_type"],
    )

    op.create_table(
        "ser_zone_streets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("zone_number", sa.String(10), nullable=False),
        sa.Column("zone_type", sa.String(50), nullable=False),
        sa.Column("street_name", sa.Text(), nullable=False),
    )
    op.create_index(
        "idx_ser_zone_streets_zone",
        "ser_zone_streets",
        ["zone_number", "zone_type"],
    )


def downgrade() -> None:
    op.drop_index("idx_ser_zone_streets_zone", table_name="ser_zone_streets")
    op.drop_table("ser_zone_streets")

    op.drop_constraint("uq_ser_zones_zone_number_zone_type", "ser_zones", type_="unique")
    op.drop_column("ser_zones", "geometry_wkt")
    op.drop_column("ser_zones", "district")
    op.drop_column("ser_zones", "zone_number")

    # Restore old point columns (empty/zero — data is not recoverable).
    op.add_column(
        "ser_zones",
        sa.Column("street_name", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "ser_zones",
        sa.Column("latitude", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "ser_zones",
        sa.Column("longitude", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "ser_zones",
        sa.Column("utm_x", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "ser_zones",
        sa.Column("utm_y", sa.Float(), nullable=False, server_default="0"),
    )
    op.create_index("idx_ser_zones_coords", "ser_zones", ["latitude", "longitude"])
