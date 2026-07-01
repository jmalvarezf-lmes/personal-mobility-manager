"""add-cascade-delete-vehicle-fks

Revision ID: a7b8c9d0e1f2
Revises: b2c3d4e5f6a1
Create Date: 2026-07-01 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # vehicle_configs: drop existing FK, recreate with ON DELETE CASCADE
    op.drop_constraint("vehicle_configs_vehicle_id_fkey", "vehicle_configs", type_="foreignkey")
    op.create_foreign_key(
        None,
        "vehicle_configs",
        "vehicles",
        ["vehicle_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # vehicle_locations: drop existing FK, recreate with ON DELETE CASCADE
    op.drop_constraint("vehicle_locations_vehicle_id_fkey", "vehicle_locations", type_="foreignkey")
    op.create_foreign_key(
        None,
        "vehicle_locations",
        "vehicles",
        ["vehicle_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # vehicle_locations: remove CASCADE FK, restore plain FK
    op.drop_constraint(None, "vehicle_locations", type_="foreignkey")  # type: ignore[arg-type]
    op.create_foreign_key(
        "vehicle_locations_vehicle_id_fkey",
        "vehicle_locations",
        "vehicles",
        ["vehicle_id"],
        ["id"],
    )

    # vehicle_configs: remove CASCADE FK, restore plain FK
    op.drop_constraint(None, "vehicle_configs", type_="foreignkey")  # type: ignore[arg-type]
    op.create_foreign_key(
        "vehicle_configs_vehicle_id_fkey",
        "vehicle_configs",
        "vehicles",
        ["vehicle_id"],
        ["id"],
    )
