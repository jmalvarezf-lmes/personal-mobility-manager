"""
Integration tests verifying the vehicle-sharing migration schema.

Requires POSTGRES_DSN environment variable.
Skipped automatically when the variable is absent.
"""

import os

import pytest
from sqlalchemy import create_engine, text


@pytest.fixture()
def pg_engine():
    dsn = os.environ.get("POSTGRES_DSN")
    if not dsn:
        pytest.skip("POSTGRES_DSN not set — skipping integration test")
    engine = create_engine(dsn, pool_pre_ping=True)
    yield engine
    engine.dispose()


def _column_exists(engine, table, column) -> bool:  # type: ignore[no-untyped-def]
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = :table AND column_name = :column
                """
            ),
            {"table": table, "column": column},
        ).fetchone()
    return row is not None


def test_vehicles_table_has_owner_id_not_user_id(pg_engine) -> None:  # type: ignore[no-untyped-def]
    assert _column_exists(pg_engine, "vehicles", "owner_id") is True
    assert _column_exists(pg_engine, "vehicles", "user_id") is False


def test_vehicle_shares_table_exists_with_composite_key(pg_engine) -> None:  # type: ignore[no-untyped-def]
    assert _column_exists(pg_engine, "vehicle_shares", "vehicle_id") is True
    assert _column_exists(pg_engine, "vehicle_shares", "user_id") is True
    assert _column_exists(pg_engine, "vehicle_shares", "created_at") is True
