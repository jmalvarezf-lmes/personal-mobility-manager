"""create-vehicle-locations

Revision ID: f3a4b5c6d1e2
Revises: e2f3a4b5c6d1
Create Date: 2026-06-28 10:02:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a4b5c6d1e2"
down_revision: str | Sequence[str] | None = "e2f3a4b5c6d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vehicle_locations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "vehicle_id",
            sa.Uuid(),
            sa.ForeignKey("vehicles.id"),
            nullable=False,
        ),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("source", sa.String(10), nullable=False),
    )
    # Composite index to speed up get_latest queries
    op.create_index(
        "ix_vehicle_locations_vehicle_recorded",
        "vehicle_locations",
        ["vehicle_id", sa.text("recorded_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_vehicle_locations_vehicle_recorded",
        table_name="vehicle_locations",
    )
    op.drop_table("vehicle_locations")
