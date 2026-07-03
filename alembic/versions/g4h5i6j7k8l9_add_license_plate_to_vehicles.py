"""add-license-plate-to-vehicles

Revision ID: g4h5i6j7k8l9
Revises: a7b8c9d0e1f2
Create Date: 2026-07-03 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g4h5i6j7k8l9"
down_revision: str | Sequence[str] | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("vehicles", sa.Column("license_plate", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("vehicles", "license_plate")
