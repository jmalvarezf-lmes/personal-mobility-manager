"""retroactive-auto-create-ticket-cascade

Revision ID: a5071149d885
Revises: 20c831d6fd2b
Create Date: 2026-07-26 00:00:00.000002

Data migration: retroactively enforce the new auto_create_ticket /
notification-preference invariant (see design.md Decision 4's transition
table) for any user who already had `user_preferences.auto_create_ticket =
true` before this change existed — the checkbox was persistable but read by
nothing until now, so no code path had ever cascaded it.

For every such user: force `ser_ticket_created` and
`ser_ticket_creation_failed` to `enabled = true`, and force
`ser_zone_ticket_required` to `enabled = false`.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a5071149d885"
down_revision: str | Sequence[str] | None = "20c831d6fd2b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE user_notification_preferences
        SET enabled = true, updated_at = now()
        WHERE type_key IN ('ser_ticket_created', 'ser_ticket_creation_failed')
          AND user_id IN (SELECT user_id FROM user_preferences WHERE auto_create_ticket = true)
        """
    )
    op.execute(
        """
        UPDATE user_notification_preferences
        SET enabled = false, updated_at = now()
        WHERE type_key = 'ser_zone_ticket_required'
          AND user_id IN (SELECT user_id FROM user_preferences WHERE auto_create_ticket = true)
        """
    )


def downgrade() -> None:
    # No down-migration: reverting this would require knowing each user's
    # prior enabled state, which wasn't recorded — matches the existing
    # precedent's rationale for irreversible data backfills.
    pass
