"""add-start-date-to-parking-tickets

Revision ID: b3e6a1c9d2f4
Revises: 7682e56d01db
Create Date: 2026-07-28 00:00:00.000000

Additive, nullable-only migration — no backfill, existing rows keep the
column NULL (there's no reliable way to recover the real parking start time
for tickets created before this field existed).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3e6a1c9d2f4"
down_revision: str | Sequence[str] | None = "7682e56d01db"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("parking_tickets", sa.Column("start_date", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("parking_tickets", "start_date")
