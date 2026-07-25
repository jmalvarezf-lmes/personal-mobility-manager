"""create_sessions_table

Revision ID: f43a41ecb8e1
Revises: b5c6d7e8f9g0
Create Date: 2026-07-25 14:42:25.952468

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f43a41ecb8e1"
down_revision: str | Sequence[str] | None = "b5c6d7e8f9g0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Create the `sessions` table (add-session-revocation).

    Autogenerate also picked up unrelated pre-existing FK/index drift on
    vehicle_ambient_labels, vehicle_configs, and vehicle_locations (their
    live DB constraints carry an ondelete=CASCADE that isn't reflected in
    tables.py's Column(ForeignKey(...)) declarations) — that drift predates
    this change and is intentionally left out of this migration; it should
    be captured by its own dedicated migration if/when addressed.

    idx_sessions_revoked_at and idx_sessions_expires_at back
    CleanupExpiredSessions/PostgresSessionRepository.delete_older_than's
    `WHERE revoked_at < cutoff OR expires_at < cutoff` query. They're two
    separate btree indexes rather than one composite index — Postgres can
    bitmap-OR two separate indexes, which suits this OR predicate better
    than a composite one — see add-session-revocation 4R review fix 3.
    """
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_sessions_user_id", "sessions", ["user_id"], unique=False)
    op.create_index("idx_sessions_revoked_at", "sessions", ["revoked_at"], unique=False)
    op.create_index("idx_sessions_expires_at", "sessions", ["expires_at"], unique=False)


def downgrade() -> None:
    """Drop the `sessions` table."""
    op.drop_index("idx_sessions_expires_at", table_name="sessions")
    op.drop_index("idx_sessions_revoked_at", table_name="sessions")
    op.drop_index("idx_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
