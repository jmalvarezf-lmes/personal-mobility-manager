"""create_ser_zones

Revision ID: 886cddfc791f
Revises:
Create Date: 2026-06-27 12:56:02.611352

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '886cddfc791f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ser_zones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("street_name", sa.Text(), nullable=False),
        sa.Column("zone_code", sa.Text(), nullable=False),
        sa.Column("zone_label", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("utm_x", sa.Float(), nullable=False),
        sa.Column("utm_y", sa.Float(), nullable=False),
    )
    op.create_index("idx_ser_zones_coords", "ser_zones", ["latitude", "longitude"])


def downgrade() -> None:
    op.drop_index("idx_ser_zones_coords", table_name="ser_zones")
    op.drop_table("ser_zones")
