"""
Integration tests for PostgresVehicleSerRequirementStateRepository and
PostgresUserSerRequirementNotificationRepository.

Requires POSTGRES_DSN environment variable.
Skipped automatically if not set.
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
                    owner_id UUID NOT NULL REFERENCES users(id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS vehicle_ser_requirement_states (
                    vehicle_id UUID PRIMARY KEY REFERENCES vehicles(id) ON DELETE CASCADE,
                    city_code TEXT,
                    zone_number TEXT,
                    is_required BOOLEAN NOT NULL,
                    activated_at TIMESTAMPTZ,
                    last_evaluated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS user_ser_requirement_notifications (
                    id UUID PRIMARY KEY,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    vehicle_id UUID NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
                    city_code TEXT,
                    zone_number TEXT,
                    latitude DOUBLE PRECISION NOT NULL,
                    longitude DOUBLE PRECISION NOT NULL,
                    requirement_activated_at TIMESTAMPTZ NOT NULL,
                    notified_at TIMESTAMPTZ NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                "TRUNCATE user_ser_requirement_notifications, vehicle_ser_requirement_states, vehicles, users CASCADE"
            )
        )
    yield engine
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE user_ser_requirement_notifications, vehicle_ser_requirement_states, vehicles, users CASCADE"
            )
        )
    engine.dispose()


def _insert_user_and_vehicle(engine):
    user_id = uuid4()
    vehicle_id = uuid4()
    now = datetime.now(UTC)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, display_name, created_at)"
                " VALUES (:id, :sub, (:id || '@example.com'), 'Test User', :now)"
            ),
            {"id": str(user_id), "sub": str(uuid4()), "now": now},
        )
        conn.execute(
            text(
                "INSERT INTO vehicles (id, brand, display_name, created_at, owner_id)"
                " VALUES (:id, 'generic', 'Test', :now, :user_id)"
            ),
            {"id": str(vehicle_id), "now": now, "user_id": str(user_id)},
        )
    return user_id, vehicle_id


def test_state_repo_returns_none_for_unknown_vehicle(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.vehicle_ser_requirement_state_repo import (
        PostgresVehicleSerRequirementStateRepository,
    )

    repo = PostgresVehicleSerRequirementStateRepository(pg_engine)
    assert repo.find_by_vehicle_id(uuid4()) is None


def test_state_repo_inserts_and_updates(pg_engine) -> None:
    from mobility_manager.domain.entities.vehicle_ser_requirement_state import (
        VehicleSerRequirementState,
    )
    from mobility_manager.infrastructure.repositories.postgres.vehicle_ser_requirement_state_repo import (
        PostgresVehicleSerRequirementStateRepository,
    )

    _, vehicle_id = _insert_user_and_vehicle(pg_engine)
    repo = PostgresVehicleSerRequirementStateRepository(pg_engine)
    now = datetime.now(UTC)

    repo.save(
        VehicleSerRequirementState(
            vehicle_id=vehicle_id,
            city_code="madrid",
            zone_number="163",
            is_required=True,
            activated_at=now,
            last_evaluated_at=now,
        )
    )

    state = repo.find_by_vehicle_id(vehicle_id)
    assert state is not None
    assert state.is_required is True
    assert state.city_code == "madrid"
    assert state.zone_number == "163"

    later = datetime.now(UTC)
    repo.save(
        VehicleSerRequirementState(
            vehicle_id=vehicle_id,
            city_code=None,
            zone_number=None,
            is_required=False,
            activated_at=None,
            last_evaluated_at=later,
        )
    )

    updated = repo.find_by_vehicle_id(vehicle_id)
    assert updated is not None
    assert updated.is_required is False
    assert updated.city_code is None
    assert updated.last_evaluated_at == later


def test_notification_audit_repo_inserts(pg_engine) -> None:
    from mobility_manager.domain.ports.user_ser_requirement_notification_repository import (
        UserSerRequirementNotification,
    )
    from mobility_manager.infrastructure.repositories.postgres.user_ser_requirement_notification_repo import (
        PostgresUserSerRequirementNotificationRepository,
    )

    user_id, vehicle_id = _insert_user_and_vehicle(pg_engine)
    repo = PostgresUserSerRequirementNotificationRepository(pg_engine)
    now = datetime.now(UTC)

    repo.save(
        UserSerRequirementNotification(
            id=uuid4(),
            user_id=user_id,
            vehicle_id=vehicle_id,
            city_code="madrid",
            zone_number="163",
            latitude=40.0,
            longitude=-3.0,
            requirement_activated_at=now,
            notified_at=now,
        )
    )

    with pg_engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM user_ser_requirement_notifications WHERE vehicle_id = :id"),
            {"id": str(vehicle_id)},
        ).fetchone()
    assert row is not None
    assert row.user_id == user_id
    assert row.city_code == "madrid"
    assert row.latitude == 40.0
