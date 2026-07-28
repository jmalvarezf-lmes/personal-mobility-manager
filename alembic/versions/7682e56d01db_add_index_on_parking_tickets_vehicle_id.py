"""add-index-on-parking-tickets-vehicle-id

Revision ID: 7682e56d01db
Revises: 9f851f2fd53d
Create Date: 2026-07-28 00:00:00.000000

Adds an index on parking_tickets.vehicle_id so `list_by_vehicle` and
`has_any_for_vehicle` (both filtered by vehicle_id only) stay index scans
instead of sequential scans as the table grows (see
add-ser-ticket-history-ui tasks.md task 14.2).
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7682e56d01db"
down_revision: str | Sequence[str] | None = "9f851f2fd53d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_parking_tickets_vehicle_id", "parking_tickets", ["vehicle_id"])


def downgrade() -> None:
    op.drop_index("ix_parking_tickets_vehicle_id", table_name="parking_tickets")
