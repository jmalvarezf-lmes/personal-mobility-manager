"""add-ser-ticket-creation-notification-types

Revision ID: 911464896d6c
Revises: f43a41ecb8e1
Create Date: 2026-07-26 00:00:00.000000

Adds the two new notification_types catalog rows introduced by
add-ser-ticket-auto-creation: `ser_ticket_created` and
`ser_ticket_creation_failed`. Both react to an event rather than gating on
movement distance, so their `config_schema` is empty (see design.md /
notification-type-preferences spec.md).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "911464896d6c"
down_revision: str | Sequence[str] | None = "f43a41ecb8e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Module-level constant (not inlined into op.bulk_insert) so
# tests/test_notification_types_migration_seed.py can import and assert
# against the actual seeded rows directly, matching the
# _THRESHOLD_CONFIG_SCHEMA pattern established by p3q4r5s6t7u8.
_SEEDED_TYPES: list[dict[str, object]] = [
    {
        "key": "ser_ticket_created",
        "label": "SER ticket created",
        "config_schema": {},
    },
    {
        "key": "ser_ticket_creation_failed",
        "label": "SER ticket creation failed",
        "config_schema": {},
    },
]


def upgrade() -> None:
    notification_types = sa.table(
        "notification_types",
        sa.column("key", sa.Text()),
        sa.column("label", sa.Text()),
        sa.column("config_schema", JSONB()),
    )
    op.bulk_insert(notification_types, _SEEDED_TYPES)


def downgrade() -> None:
    op.execute(
        "DELETE FROM notification_types WHERE key IN ('ser_ticket_created', 'ser_ticket_creation_failed')"
    )
