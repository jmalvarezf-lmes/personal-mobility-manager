"""backfill-user-notification-preferences

Revision ID: r5s6t7u8v9w0
Revises: q4r5s6t7u8v9
Create Date: 2026-07-16 00:00:00.000000

Data migration: insert a disabled (enabled=false, config={}) preference row
for every existing users x notification_types pair that doesn't already have
one. This is an explicit opt-in migration — it intentionally does not carry
forward the prior unconditional-notification behavior, since no user had
ever previously consented to either notification kind per type (see
proposal.md / design.md decision 3).

ON CONFLICT DO NOTHING makes this idempotent: re-running it after a partial
failure never duplicates or overwrites an existing row.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "r5s6t7u8v9w0"
down_revision: str | Sequence[str] | None = "q4r5s6t7u8v9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO user_notification_preferences (user_id, type_key, enabled, config, updated_at)
        SELECT users.id, notification_types.key, false, '{}'::jsonb, now()
        FROM users
        CROSS JOIN notification_types
        ON CONFLICT (user_id, type_key) DO NOTHING
        """
    )


def downgrade() -> None:
    # No down-migration: dropping the backfilled rows is destructive and not
    # required for rollback (see design.md Migration Plan — the new tables
    # can remain unused after reverting handler code).
    pass
