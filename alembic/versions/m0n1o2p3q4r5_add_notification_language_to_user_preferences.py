"""add-notification-language-to-user-preferences

Revision ID: m0n1o2p3q4r5
Revises: l9m0n1o2p3q4
Create Date: 2026-07-06 23:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m0n1o2p3q4r5"
down_revision: str | Sequence[str] | None = "l9m0n1o2p3q4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_preferences",
        sa.Column("notification_language", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "notification_language")
