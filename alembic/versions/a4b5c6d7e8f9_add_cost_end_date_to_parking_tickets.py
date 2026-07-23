"""add-cost-end-date-to-parking-tickets

Revision ID: a4b5c6d7e8f9
Revises: z3a4b5c6d7e8
Create Date: 2026-07-23 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4b5c6d7e8f9"
down_revision: str | Sequence[str] | None = "z3a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # parking_tickets is a leaf table (no downstream FK dependents) — truncate
    # before adding NOT NULL columns, mirroring b2c3d4e5f6a1's precedent.
    # Every ticket created going forward populates cost/end_date (see
    # design.md Migration Plan #1).
    op.execute("TRUNCATE TABLE parking_tickets")
    op.add_column("parking_tickets", sa.Column("cost", sa.Numeric(), nullable=False))
    op.add_column("parking_tickets", sa.Column("end_date", sa.DateTime(timezone=True), nullable=False))


def downgrade() -> None:
    op.drop_column("parking_tickets", "end_date")
    op.drop_column("parking_tickets", "cost")
