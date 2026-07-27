"""add_zone_to_parking_tickets

Revision ID: 7ef5def2952a
Revises: a5071149d885
Create Date: 2026-07-27 16:34:09.465910

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7ef5def2952a'
down_revision: Union[str, Sequence[str], None] = 'a5071149d885'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Additive, nullable-only migration (see design.md Migration Plan) — no
    # backfill, existing rows keep both columns NULL.
    #
    # Autogenerate also detected unrelated pre-existing drift between the ORM
    # metadata and the live schema (vehicle_configs/vehicle_locations/
    # vehicle_ambient_labels foreign-key ondelete clauses and two indexes not
    # modeled in tables.py). That drift predates this change and is
    # deliberately NOT included here to keep this migration scoped to the
    # ser-ticket-zone-gate change only.
    op.add_column('parking_tickets', sa.Column('city_code', sa.Text(), nullable=True))
    op.add_column('parking_tickets', sa.Column('zone_number', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('parking_tickets', 'zone_number')
    op.drop_column('parking_tickets', 'city_code')
