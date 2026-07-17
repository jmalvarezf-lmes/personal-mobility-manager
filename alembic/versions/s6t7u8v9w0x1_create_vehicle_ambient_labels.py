"""create-vehicle-ambient-labels

Revision ID: s6t7u8v9w0x1
Revises: r5s6t7u8v9w0
Create Date: 2026-07-17 00:00:00.000000

Additive-only migration: adds `vehicle_ambient_labels` (1:1 with vehicles,
mirrors the vehicle_configs shape) and `ambient_label_icons` (a small cache
table keyed by label value, shared across every vehicle with that label).
No changes to any existing table.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "s6t7u8v9w0x1"
down_revision: str | Sequence[str] | None = "r5s6t7u8v9w0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vehicle_ambient_labels",
        sa.Column(
            "vehicle_id",
            sa.Uuid(),
            sa.ForeignKey("vehicles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("label", sa.String(10), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "ambient_label_icons",
        sa.Column("label", sa.String(10), primary_key=True),
        sa.Column("image_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ambient_label_icons")
    op.drop_table("vehicle_ambient_labels")
