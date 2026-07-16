"""create-notification-types

Revision ID: p3q4r5s6t7u8
Revises: o2p3q4r5s6t7
Create Date: 2026-07-16 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "p3q4r5s6t7u8"
down_revision: str | Sequence[str] | None = "o2p3q4r5s6t7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Must stay a dict, not a json.dumps() string: the JSONB adapter already
# serializes Python objects to JSON, so passing a pre-serialized string here
# double-encodes it into a JSON *string value* instead of a JSON *object* —
# which round-trips back as a Python str, not a dict, and fails
# NotificationTypeResponse's pydantic validation on every GET /notifications/types.
_THRESHOLD_CONFIG_SCHEMA = {"threshold_m": {"type": "integer", "min": 1}}


def upgrade() -> None:
    op.create_table(
        "notification_types",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("config_schema", JSONB(), nullable=False),
    )

    notification_types = sa.table(
        "notification_types",
        sa.column("key", sa.Text()),
        sa.column("label", sa.Text()),
        sa.column("config_schema", JSONB()),
    )
    op.bulk_insert(
        notification_types,
        [
            {
                "key": "location_moved",
                "label": "Vehicle moved",
                "config_schema": _THRESHOLD_CONFIG_SCHEMA,
            },
            {
                "key": "ser_zone_ticket_required",
                "label": "SER ticket required",
                "config_schema": _THRESHOLD_CONFIG_SCHEMA,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("notification_types")
