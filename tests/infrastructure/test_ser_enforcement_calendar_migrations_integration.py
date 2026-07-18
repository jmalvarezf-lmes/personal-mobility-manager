"""
Integration test: add-ser-enforcement-calendar migrations apply cleanly
end-to-end and seeded data matches the `city-registry`/`ser-enforcement-schedule`
spec scenarios.

Unlike the other `*_repo_integration.py` files (which hand-author a minimal
schema via CREATE TABLE IF NOT EXISTS against POSTGRES_DSN, then exercise a
repository class), this test's whole purpose is verifying the *migration
files themselves* — so it runs `alembic upgrade head` programmatically
against POSTGRES_DSN (the same DSN + connection convention every other
`*_repo_integration.py` file already uses) and then asserts on the
resulting seeded rows.

Requires POSTGRES_DSN to point at a reachable PostgreSQL instance.
Skipped if POSTGRES_DSN is unset; if POSTGRES_DSN is set but unreachable
(e.g. this repo's .env.example/.env convention of pointing at the
docker-compose `postgres` hostname, which does not resolve outside a
container), this test errors at fixture setup for the same DB-unreachable
reason every other `*_repo_integration.py` file does in that environment —
this is expected and consistent with the existing baseline, not a new
failure mode.
"""

import os
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command

_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def pg_engine():
    """Create a SQLAlchemy engine from POSTGRES_DSN env var, or skip if not set."""
    dsn = os.environ.get("POSTGRES_DSN")
    if not dsn:
        pytest.skip("POSTGRES_DSN environment variable not set — skipping integration test")
    engine = create_engine(dsn, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(
            text("SELECT 1")
        )  # force a real connection attempt now, matching sibling *_repo_integration.py fixtures
    yield engine
    engine.dispose()


def test_migrations_apply_cleanly_and_seed_data_matches_spec(pg_engine) -> None:
    cfg = Config(str(_REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_REPO_ROOT / "alembic"))
    command.upgrade(cfg, "head")

    with pg_engine.connect() as conn:
        # cities: seeded madrid row (city-registry spec)
        cities = conn.execute(text("SELECT code, name FROM cities WHERE code = 'madrid'")).fetchall()
        assert len(cities) == 1
        assert cities[0][1] == "Madrid"

        # ser_timetable_weekday_hours: 7 rows for madrid matching Madrid's published hours
        weekday_rows = conn.execute(
            text(
                "SELECT weekday, start_time, end_time, active "
                "FROM ser_timetable_weekday_hours WHERE city_code = 'madrid' ORDER BY weekday"
            )
        ).fetchall()
        assert len(weekday_rows) == 7

        weekday_by_index = {row[0]: row for row in weekday_rows}
        for weekday in range(5):  # Mon-Fri: 09:00-21:00, active
            row = weekday_by_index[weekday]
            assert str(row[1]) == "09:00:00"
            assert str(row[2]) == "21:00:00"
            assert row[3] is True

        saturday = weekday_by_index[5]
        assert str(saturday[1]) == "09:00:00"
        assert str(saturday[2]) == "15:00:00"
        assert saturday[3] is True

        sunday = weekday_by_index[6]
        assert sunday[3] is False

        # ser_timetable_exception: 3 rows for madrid (August, Dec 24, Dec 31)
        exception_rows = conn.execute(
            text(
                "SELECT recurrence, month, month_day, start_time, end_time "
                "FROM ser_timetable_exception WHERE city_code = 'madrid' ORDER BY id"
            )
        ).fetchall()
        assert len(exception_rows) == 3

        month_exceptions = [row for row in exception_rows if row[0] == "month"]
        fixed_date_exceptions = [row for row in exception_rows if row[0] == "fixed_date"]

        assert len(month_exceptions) == 1
        assert month_exceptions[0][1] == 8  # August
        assert month_exceptions[0][2] is None
        assert str(month_exceptions[0][3]) == "09:00:00"
        assert str(month_exceptions[0][4]) == "15:00:00"

        assert len(fixed_date_exceptions) == 2
        month_days = {row[2] for row in fixed_date_exceptions}
        assert month_days == {"12-24", "12-31"}
        for row in fixed_date_exceptions:
            assert row[1] is None
            assert str(row[3]) == "09:00:00"
            assert str(row[4]) == "15:00:00"

        # holidays: schema-only, no seed rows
        holiday_count = conn.execute(text("SELECT COUNT(*) FROM holidays")).scalar()
        assert holiday_count == 0
