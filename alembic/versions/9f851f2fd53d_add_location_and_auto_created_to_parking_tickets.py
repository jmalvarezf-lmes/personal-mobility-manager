"""add-location-and-auto-created-to-parking-tickets

Revision ID: 9f851f2fd53d
Revises: 7ef5def2952a
Create Date: 2026-07-28 00:00:00.000000

Additive, nullable-only migration (see add-ser-ticket-history-ui design.md
Migration Plan) — no backfill, existing rows keep all three columns NULL.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9f851f2fd53d"
down_revision: str | Sequence[str] | None = "7ef5def2952a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("parking_tickets", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("parking_tickets", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column("parking_tickets", sa.Column("auto_created", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("parking_tickets", "auto_created")
    op.drop_column("parking_tickets", "longitude")
    op.drop_column("parking_tickets", "latitude")
