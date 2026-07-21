"""add-timezone-to-user-preferences

Revision ID: z3a4b5c6d7e8
Revises: y2z3a4b5c6d7
Create Date: 2026-07-21 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "z3a4b5c6d7e8"
down_revision: str | Sequence[str] | None = "y2z3a4b5c6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_preferences",
        sa.Column("timezone", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "timezone")
