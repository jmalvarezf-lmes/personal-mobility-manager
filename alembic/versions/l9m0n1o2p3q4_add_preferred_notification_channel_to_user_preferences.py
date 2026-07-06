"""add-preferred-notification-channel-to-user-preferences

Revision ID: l9m0n1o2p3q4
Revises: k8l9m0n1o2p3
Create Date: 2026-07-06 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "l9m0n1o2p3q4"
down_revision: str | Sequence[str] | None = "k8l9m0n1o2p3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_preferences",
        sa.Column("preferred_notification_channel", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "preferred_notification_channel")
