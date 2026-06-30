"""add-user-id-to-vehicles

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-06-30 10:01:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a1"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Truncate dependent tables in FK order before adding NOT NULL column
    op.execute("TRUNCATE TABLE vehicle_locations, vehicle_configs, vehicles CASCADE")
    op.add_column(
        "vehicles",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("vehicles", "user_id")
