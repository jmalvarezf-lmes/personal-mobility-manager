"""create-vehicle-configs

Revision ID: e2f3a4b5c6d1
Revises: d1e2f3a4b5c6
Create Date: 2026-06-28 10:01:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2f3a4b5c6d1"
down_revision: str | Sequence[str] | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vehicle_configs",
        sa.Column(
            "vehicle_id",
            sa.Uuid(),
            sa.ForeignKey("vehicles.id"),
            primary_key=True,
        ),
        sa.Column("brand", sa.String(20), nullable=False),
        sa.Column("encrypted_payload", sa.LargeBinary(), nullable=True),
        sa.Column("location_token", sa.String(64), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    # Partial index for O(1) token lookup on the push endpoint
    op.create_index(
        "ix_vehicle_configs_location_token",
        "vehicle_configs",
        ["location_token"],
        postgresql_where=sa.text("location_token IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_vehicle_configs_location_token", table_name="vehicle_configs")
    op.drop_table("vehicle_configs")
