"""backfill-ser-ticket-creation-preferences

Revision ID: 20c831d6fd2b
Revises: 911464896d6c
Create Date: 2026-07-26 00:00:00.000001

Data migration: insert a disabled (enabled=false, config={}) preference row
for every existing user x {ser_ticket_created, ser_ticket_creation_failed}
pair that doesn't already have one — same idempotent pattern as
r5s6t7u8v9w0_backfill_user_notification_preferences.py.

ON CONFLICT DO NOTHING makes this safe to re-run.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20c831d6fd2b"
down_revision: str | Sequence[str] | None = "911464896d6c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO user_notification_preferences (user_id, type_key, enabled, config, updated_at)
        SELECT users.id, notification_types.key, false, '{}'::jsonb, now()
        FROM users
        CROSS JOIN notification_types
        WHERE notification_types.key IN ('ser_ticket_created', 'ser_ticket_creation_failed')
        ON CONFLICT (user_id, type_key) DO NOTHING
        """
    )


def downgrade() -> None:
    # No down-migration: dropping the backfilled rows is destructive and not
    # required for rollback (see design.md Migration Plan).
    pass
