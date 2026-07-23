"""create-ser-ticket-provider-zone-mappings

Revision ID: b5c6d7e8f9g0
Revises: a4b5c6d7e8f9
Create Date: 2026-07-23 00:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5c6d7e8f9g0"
down_revision: str | Sequence[str] | None = "a4b5c6d7e8f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ser_ticket_provider_zone_mappings",
        sa.Column("city_code", sa.Text(), sa.ForeignKey("cities.code"), primary_key=True),
        sa.Column("provider", sa.Text(), primary_key=True),
        sa.Column("id_ser_town", sa.Text(), nullable=False),
        sa.Column("zones_payload", JSONB(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ser_ticket_provider_zone_mappings")
