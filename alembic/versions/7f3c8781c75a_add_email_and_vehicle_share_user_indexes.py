"""add email and vehicle share user indexes

Revision ID: 7f3c8781c75a
Revises: acb7f672fe8c
Create Date: 2026-08-20 00:37:52.242193

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7f3c8781c75a"
down_revision: str | Sequence[str] | None = "acb7f672fe8c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Case-insensitive unique index on user emails. This both enforces that
    # two accounts cannot share the same email (regardless of casing) and
    # accelerates the email lookup used by vehicle sharing.
    op.create_index(
        "idx_users_email_lower",
        "users",
        [sa.func.lower(sa.column("email"))],
        unique=True,
    )
    # Index on the trailing column of the vehicle_shares composite PK so
    # list_vehicle_ids_for_user does not table-scan as sharing grows.
    op.create_index(
        "idx_vehicle_shares_user_id",
        "vehicle_shares",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_vehicle_shares_user_id", table_name="vehicle_shares")
    op.drop_index("idx_users_email_lower", table_name="users")
