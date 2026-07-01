"""
Integration tests for PostgresVehicleRepository.get_all_by_user_id.

Requires POSTGRES_DSN environment variable.
Skipped automatically when the variable is absent.
"""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text


@pytest.fixture()
def pg_engine():
    dsn = os.environ.get("POSTGRES_DSN")
    if not dsn:
        pytest.skip("POSTGRES_DSN not set — skipping integration test")
    engine = create_engine(dsn, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY,
                    google_sub TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS vehicles (
                    id UUID PRIMARY KEY,
                    brand VARCHAR(20) NOT NULL,
                    display_name VARCHAR(255) NOT NULL,
                    vin VARCHAR(50),
                    created_at TIMESTAMPTZ NOT NULL,
                    user_id UUID NOT NULL REFERENCES users(id)
                )
                """
            )
        )
        conn.execute(text("TRUNCATE vehicles, users CASCADE"))
    yield engine
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE vehicles, users CASCADE"))
    engine.dispose()


def _insert_user(engine, user_id) -> None:  # type: ignore[no-untyped-def]
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, display_name, created_at)"
                " VALUES (:id, :sub, 'test@example.com', 'Test User', :now)"
            ),
            {"id": str(user_id), "sub": str(uuid4()), "now": datetime.now(UTC)},
        )


def _insert_vehicle(engine, vehicle_id, user_id, brand="generic") -> None:  # type: ignore[no-untyped-def]
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO vehicles (id, brand, display_name, created_at, user_id)"
                " VALUES (:id, :brand, 'Test Car', :now, :user_id)"
            ),
            {"id": str(vehicle_id), "brand": brand, "now": datetime.now(UTC), "user_id": str(user_id)},
        )


def test_get_all_by_user_id_returns_owned_vehicles(pg_engine) -> None:  # type: ignore[no-untyped-def]
    from mobility_manager.infrastructure.repositories.postgres.vehicle_repo import (
        PostgresVehicleRepository,
    )

    user_a = uuid4()
    user_b = uuid4()
    _insert_user(pg_engine, user_a)
    _insert_user(pg_engine, user_b)

    v1 = uuid4()
    v2 = uuid4()
    v3 = uuid4()
    _insert_vehicle(pg_engine, v1, user_a)
    _insert_vehicle(pg_engine, v2, user_a)
    _insert_vehicle(pg_engine, v3, user_b)

    repo = PostgresVehicleRepository(pg_engine)

    vehicles_a = repo.get_all_by_user_id(user_a)
    vehicles_b = repo.get_all_by_user_id(user_b)

    assert len(vehicles_a) == 2
    assert all(v.user_id == user_a for v in vehicles_a)

    assert len(vehicles_b) == 1
    assert vehicles_b[0].user_id == user_b


def test_get_all_by_user_id_empty_for_unknown_user(pg_engine) -> None:  # type: ignore[no-untyped-def]
    from mobility_manager.infrastructure.repositories.postgres.vehicle_repo import (
        PostgresVehicleRepository,
    )

    repo = PostgresVehicleRepository(pg_engine)
    assert repo.get_all_by_user_id(uuid4()) == []
