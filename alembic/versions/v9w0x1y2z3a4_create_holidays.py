"""create-holidays

Revision ID: v9w0x1y2z3a4
Revises: u8v9w0x1y2z3
Create Date: 2026-07-18 00:00:00.000000

Schema-only migration: no seed rows. The first data arrives via the
public-holiday-calendar refresh job's startup-conditional fetch (see
design.md D8) — a later chunk of this change, not this migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "v9w0x1y2z3a4"
down_revision: str | Sequence[str] | None = "u8v9w0x1y2z3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "holidays",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("city_code", sa.Text(), sa.ForeignKey("cities.code"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),  # 'ical_national' | 'manual'
        sa.UniqueConstraint("city_code", "date", "source", name="uq_holidays_city_date_source"),
    )


def downgrade() -> None:
    op.drop_table("holidays")
