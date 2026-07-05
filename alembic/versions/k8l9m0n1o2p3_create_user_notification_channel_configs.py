"""create-user-notification-channel-configs

Revision ID: k8l9m0n1o2p3
Revises: j7k8l9m0n1o2
Create Date: 2026-07-05 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "k8l9m0n1o2p3"
down_revision: str | Sequence[str] | None = "j7k8l9m0n1o2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_notification_channel_configs",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id"),
            primary_key=True,
        ),
        sa.Column("channel", sa.Text(), primary_key=True),
        # Cleartext JSON — not encrypted. A channel identifier such as a
        # Telegram chat_id is not a credential, unlike SER provider sessions.
        sa.Column("config", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_notification_channel_configs")
