"""create-ser-enforcement-timetable

Revision ID: u8v9w0x1y2z3
Revises: t7u8v9w0x1y2
Create Date: 2026-07-18 00:00:00.000000

Schema + seed data for Madrid's published SER enforcement hours (see
design.md D2). No external datasource: the timetable is fixed and
hand-authored directly into this migration.
"""

from collections.abc import Sequence
from datetime import time

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "u8v9w0x1y2z3"
down_revision: str | Sequence[str] | None = "t7u8v9w0x1y2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ser_timetable_weekday_hours",
        sa.Column("city_code", sa.Text(), sa.ForeignKey("cities.code"), primary_key=True),
        sa.Column("weekday", sa.SmallInteger(), primary_key=True),  # 0=Monday..6=Sunday
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
    )

    op.create_table(
        "ser_timetable_exception",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("city_code", sa.Text(), sa.ForeignKey("cities.code"), nullable=False),
        sa.Column("recurrence", sa.Text(), nullable=False),  # 'month' | 'fixed_date'
        sa.Column("month", sa.SmallInteger(), nullable=True),  # populated only for recurrence='month'
        sa.Column("month_day", sa.Text(), nullable=True),  # 'MM-DD', populated only for recurrence='fixed_date'
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
    )

    weekday_hours = sa.table(
        "ser_timetable_weekday_hours",
        sa.column("city_code", sa.Text()),
        sa.column("weekday", sa.SmallInteger()),
        sa.column("start_time", sa.Time()),
        sa.column("end_time", sa.Time()),
        sa.column("active", sa.Boolean()),
    )
    op.bulk_insert(
        weekday_hours,
        [
            {"city_code": "madrid", "weekday": 0, "start_time": time(9, 0), "end_time": time(21, 0), "active": True},
            {"city_code": "madrid", "weekday": 1, "start_time": time(9, 0), "end_time": time(21, 0), "active": True},
            {"city_code": "madrid", "weekday": 2, "start_time": time(9, 0), "end_time": time(21, 0), "active": True},
            {"city_code": "madrid", "weekday": 3, "start_time": time(9, 0), "end_time": time(21, 0), "active": True},
            {"city_code": "madrid", "weekday": 4, "start_time": time(9, 0), "end_time": time(21, 0), "active": True},
            {"city_code": "madrid", "weekday": 5, "start_time": time(9, 0), "end_time": time(15, 0), "active": True},
            {
                "city_code": "madrid",
                "weekday": 6,
                "start_time": time(9, 0),
                "end_time": time(15, 0),
                "active": False,
            },
        ],
    )

    exceptions = sa.table(
        "ser_timetable_exception",
        sa.column("city_code", sa.Text()),
        sa.column("recurrence", sa.Text()),
        sa.column("month", sa.SmallInteger()),
        sa.column("month_day", sa.Text()),
        sa.column("start_time", sa.Time()),
        sa.column("end_time", sa.Time()),
        sa.column("description", sa.Text()),
    )
    op.bulk_insert(
        exceptions,
        [
            {
                "city_code": "madrid",
                "recurrence": "month",
                "month": 8,
                "month_day": None,
                "start_time": time(9, 0),
                "end_time": time(15, 0),
                "description": "August reduced hours",
            },
            {
                "city_code": "madrid",
                "recurrence": "fixed_date",
                "month": None,
                "month_day": "12-24",
                "start_time": time(9, 0),
                "end_time": time(15, 0),
                "description": "Christmas Eve reduced hours",
            },
            {
                "city_code": "madrid",
                "recurrence": "fixed_date",
                "month": None,
                "month_day": "12-31",
                "start_time": time(9, 0),
                "end_time": time(15, 0),
                "description": "New Year's Eve reduced hours",
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("ser_timetable_exception")
    op.drop_table("ser_timetable_weekday_hours")
