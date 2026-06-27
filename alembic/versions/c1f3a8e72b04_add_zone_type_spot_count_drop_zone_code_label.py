"""add-zone-type-spot-count-drop-zone-code-label

Revision ID: c1f3a8e72b04
Revises: 886cddfc791f
Create Date: 2026-06-27 19:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c1f3a8e72b04"
down_revision: Union[str, Sequence[str], None] = "886cddfc791f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns
    op.add_column(
        "ser_zones",
        sa.Column(
            "zone_type",
            sa.String(50),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "ser_zones",
        sa.Column(
            "spot_count",
            sa.Integer(),
            nullable=False,
            server_default="-1",
        ),
    )

    # Drop old columns
    op.drop_column("ser_zones", "zone_code")
    op.drop_column("ser_zones", "zone_label")


def downgrade() -> None:
    # Restore old columns (empty strings — data is not recoverable)
    op.add_column(
        "ser_zones",
        sa.Column("zone_code", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "ser_zones",
        sa.Column("zone_label", sa.Text(), nullable=False, server_default=""),
    )

    # Drop new columns
    op.drop_column("ser_zones", "spot_count")
    op.drop_column("ser_zones", "zone_type")
