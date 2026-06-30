"""
Integration tests for PostgresVehicleLocationRepository.

Requires POSTGRES_DSN environment variable.
Skipped automatically if not set.
"""

import os
from datetime import UTC, datetime, timedelta
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
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS vehicle_locations (
                    id UUID PRIMARY KEY,
                    vehicle_id UUID NOT NULL REFERENCES vehicles(id),
                    latitude DOUBLE PRECISION NOT NULL,
                    longitude DOUBLE PRECISION NOT NULL,
                    recorded_at TIMESTAMPTZ NOT NULL,
                    received_at TIMESTAMPTZ NOT NULL,
                    source VARCHAR(10) NOT NULL
                )
                """
            )
        )
        conn.execute(text("TRUNCATE vehicle_locations, vehicles, users CASCADE"))
    yield engine
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE vehicle_locations, vehicles, users CASCADE"))
    engine.dispose()


def _insert_vehicle(engine, vehicle_id) -> None:
    user_id = uuid4()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, display_name, created_at)"
                " VALUES (:id, :sub, 'test@example.com', 'Test User', :now)"
            ),
            {"id": str(user_id), "sub": str(uuid4()), "now": datetime.now(UTC)},
        )
        conn.execute(
            text(
                "INSERT INTO vehicles (id, brand, display_name, created_at, user_id)"
                " VALUES (:id, 'generic', 'Test', :now, :user_id)"
            ),
            {"id": str(vehicle_id), "now": datetime.now(UTC), "user_id": str(user_id)},
        )


def test_get_latest_returns_none_for_unknown_vehicle(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.vehicle_location_repo import (
        PostgresVehicleLocationRepository,
    )

    repo = PostgresVehicleLocationRepository(pg_engine)
    result = repo.get_latest(uuid4())
    assert result is None


def test_get_latest_returns_most_recent_row(pg_engine) -> None:
    from mobility_manager.domain.entities.vehicle_location import VehicleLocation
    from mobility_manager.infrastructure.repositories.postgres.vehicle_location_repo import (
        PostgresVehicleLocationRepository,
    )

    repo = PostgresVehicleLocationRepository(pg_engine)
    vehicle_id = uuid4()
    _insert_vehicle(pg_engine, vehicle_id)

    now = datetime.now(UTC)
    old_loc = VehicleLocation(
        id=uuid4(),
        vehicle_id=vehicle_id,
        latitude=1.0,
        longitude=1.0,
        recorded_at=now - timedelta(hours=1),
        received_at=now - timedelta(hours=1),
        source="pull",
    )
    new_loc = VehicleLocation(
        id=uuid4(),
        vehicle_id=vehicle_id,
        latitude=2.0,
        longitude=2.0,
        recorded_at=now,
        received_at=now,
        source="push",
    )

    repo.save(old_loc)
    repo.save(new_loc)

    latest = repo.get_latest(vehicle_id)
    assert latest is not None
    assert latest.latitude == 2.0
    assert latest.source == "push"


def test_save_accumulates_rows(pg_engine) -> None:
    from mobility_manager.domain.entities.vehicle_location import VehicleLocation
    from mobility_manager.infrastructure.repositories.postgres.vehicle_location_repo import (
        PostgresVehicleLocationRepository,
    )

    repo = PostgresVehicleLocationRepository(pg_engine)
    vehicle_id = uuid4()
    _insert_vehicle(pg_engine, vehicle_id)

    now = datetime.now(UTC)
    for i in range(3):
        repo.save(
            VehicleLocation(
                id=uuid4(),
                vehicle_id=vehicle_id,
                latitude=float(i),
                longitude=0.0,
                recorded_at=now + timedelta(minutes=i),
                received_at=now,
                source="pull",
            )
        )

    with pg_engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM vehicle_locations WHERE vehicle_id = :id"),
            {"id": str(vehicle_id)},
        ).scalar()
    assert count == 3


def test_get_latest_uses_recorded_at_not_received_at(pg_engine) -> None:
    """Ensure ordering is by recorded_at, not received_at."""
    from mobility_manager.domain.entities.vehicle_location import VehicleLocation
    from mobility_manager.infrastructure.repositories.postgres.vehicle_location_repo import (
        PostgresVehicleLocationRepository,
    )

    repo = PostgresVehicleLocationRepository(pg_engine)
    vehicle_id = uuid4()
    _insert_vehicle(pg_engine, vehicle_id)

    now = datetime.now(UTC)
    # older received_at but newer recorded_at
    loc_a = VehicleLocation(
        id=uuid4(),
        vehicle_id=vehicle_id,
        latitude=10.0,
        longitude=0.0,
        recorded_at=now + timedelta(hours=1),  # newer GPS time
        received_at=now - timedelta(hours=2),  # older server receipt
        source="push",
    )
    loc_b = VehicleLocation(
        id=uuid4(),
        vehicle_id=vehicle_id,
        latitude=20.0,
        longitude=0.0,
        recorded_at=now - timedelta(hours=1),  # older GPS time
        received_at=now,  # newer server receipt
        source="pull",
    )
    repo.save(loc_a)
    repo.save(loc_b)

    latest = repo.get_latest(vehicle_id)
    assert latest is not None
    assert latest.latitude == 10.0  # loc_a has higher recorded_at
