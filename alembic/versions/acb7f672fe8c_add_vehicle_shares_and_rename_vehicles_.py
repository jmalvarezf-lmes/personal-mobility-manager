"""add_vehicle_shares_and_rename_vehicles_user_id_to_owner_id

Revision ID: acb7f672fe8c
Revises: b3e6a1c9d2f4
Create Date: 2026-08-19 00:05:32.310802

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "acb7f672fe8c"
down_revision: str | Sequence[str] | None = "b3e6a1c9d2f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vehicle_shares",
        sa.Column(
            "vehicle_id",
            sa.Uuid(),
            sa.ForeignKey("vehicles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute(
        "ALTER TABLE vehicles RENAME COLUMN user_id TO owner_id; "
        "ALTER TABLE vehicles RENAME CONSTRAINT vehicles_user_id_fkey TO vehicles_owner_id_fkey;"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE vehicles RENAME COLUMN owner_id TO user_id; "
        "ALTER TABLE vehicles RENAME CONSTRAINT vehicles_owner_id_fkey TO vehicles_user_id_fkey;"
    )
    op.drop_table("vehicle_shares")
