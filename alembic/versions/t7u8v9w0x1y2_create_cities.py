"""create-cities

Revision ID: t7u8v9w0x1y2
Revises: s6t7u8v9w0x1
Create Date: 2026-07-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "t7u8v9w0x1y2"
down_revision: str | Sequence[str] | None = "s6t7u8v9w0x1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cities",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
    )

    cities = sa.table(
        "cities",
        sa.column("code", sa.Text()),
        sa.column("name", sa.Text()),
    )
    op.bulk_insert(
        cities,
        [{"code": "madrid", "name": "Madrid"}],
    )


def downgrade() -> None:
    op.drop_table("cities")
