"""add-ser-zone-frontiers

Revision ID: o2p3q4r5s6t7
Revises: n1o2p3q4r5s6
Create Date: 2026-07-11 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "o2p3q4r5s6t7"
down_revision: str | Sequence[str] | None = "n1o2p3q4r5s6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ser_zone_areas",
        sa.Column("zone_number", sa.String(10), primary_key=True),
        sa.Column("neighbourhood", sa.Text(), nullable=False),
        sa.Column("geometry_wkt", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ser_zone_areas")
