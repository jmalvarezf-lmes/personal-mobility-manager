"""
Integration tests for PostgresVehicleAmbientLabelRepository and
PostgresAmbientLabelIconRepository.

Requires POSTGRES_DSN environment variable. Skipped automatically if absent,
mirroring tests/infrastructure/test_vehicle_config_repo_integration.py.
"""

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from mobility_manager.domain.value_objects.ambient_label import AmbientLabel
from mobility_manager.domain.value_objects.ambient_label_status import (
    AmbientLabelStatus,
)
from mobility_manager.infrastructure.repositories.postgres.ambient_label_icon_repo import (
    PostgresAmbientLabelIconRepository,
)
from mobility_manager.infrastructure.repositories.postgres.vehicle_ambient_label_repo import (
    PostgresVehicleAmbientLabelRepository,
)


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
                    license_plate VARCHAR(20),
                    created_at TIMESTAMPTZ NOT NULL,
                    user_id UUID NOT NULL REFERENCES users(id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS vehicle_ambient_labels (
                    vehicle_id UUID PRIMARY KEY REFERENCES vehicles(id) ON DELETE CASCADE,
                    label VARCHAR(10),
                    status VARCHAR(20) NOT NULL,
                    last_checked_at TIMESTAMPTZ
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS ambient_label_icons (
                    label VARCHAR(10) PRIMARY KEY,
                    image_bytes BYTEA NOT NULL,
                    content_type VARCHAR(100) NOT NULL,
                    fetched_at TIMESTAMPTZ NOT NULL
                )
                """
            )
        )
        conn.execute(text("TRUNCATE vehicle_ambient_labels, ambient_label_icons, vehicles, users CASCADE"))
    yield engine
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE vehicle_ambient_labels, ambient_label_icons, vehicles, users CASCADE"))
    engine.dispose()


def _insert_vehicle(engine, vehicle_id, license_plate: str | None = "1234ABC") -> None:
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
                "INSERT INTO vehicles (id, brand, display_name, license_plate, created_at, user_id)"
                " VALUES (:id, 'generic', 'Test', :plate, :now, :user_id)"
            ),
            {
                "id": str(vehicle_id),
                "plate": license_plate,
                "now": datetime.now(UTC),
                "user_id": str(user_id),
            },
        )


# ---------------------------------------------------------------------------
# PostgresVehicleAmbientLabelRepository
# ---------------------------------------------------------------------------


def test_upsert_found_then_get_by_vehicle_id(pg_engine) -> None:
    repo = PostgresVehicleAmbientLabelRepository(pg_engine)
    vehicle_id = uuid4()
    _insert_vehicle(pg_engine, vehicle_id)
    now = datetime.now(UTC)

    repo.upsert(vehicle_id, AmbientLabel.B, AmbientLabelStatus.FOUND, now)
    row = repo.get_by_vehicle_id(vehicle_id)

    assert row is not None
    assert row.label == AmbientLabel.B
    assert row.status == AmbientLabelStatus.FOUND


def test_upsert_not_found_has_null_label(pg_engine) -> None:
    repo = PostgresVehicleAmbientLabelRepository(pg_engine)
    vehicle_id = uuid4()
    _insert_vehicle(pg_engine, vehicle_id)

    repo.upsert(vehicle_id, None, AmbientLabelStatus.NOT_FOUND, datetime.now(UTC))
    row = repo.get_by_vehicle_id(vehicle_id)

    assert row is not None
    assert row.label is None
    assert row.status == AmbientLabelStatus.NOT_FOUND


def test_upsert_overwrites_existing_row(pg_engine) -> None:
    repo = PostgresVehicleAmbientLabelRepository(pg_engine)
    vehicle_id = uuid4()
    _insert_vehicle(pg_engine, vehicle_id)

    repo.upsert(vehicle_id, None, AmbientLabelStatus.ERROR, datetime.now(UTC))
    repo.upsert(vehicle_id, AmbientLabel.ECO, AmbientLabelStatus.FOUND, datetime.now(UTC))

    row = repo.get_by_vehicle_id(vehicle_id)
    assert row is not None
    assert row.label == AmbientLabel.ECO
    assert row.status == AmbientLabelStatus.FOUND


def test_get_by_vehicle_id_returns_none_when_absent(pg_engine) -> None:
    repo = PostgresVehicleAmbientLabelRepository(pg_engine)
    assert repo.get_by_vehicle_id(uuid4()) is None


def test_backlog_includes_vehicle_with_no_row(pg_engine) -> None:
    repo = PostgresVehicleAmbientLabelRepository(pg_engine)
    vehicle_id = uuid4()
    _insert_vehicle(pg_engine, vehicle_id)

    backlog = repo.get_vehicles_needing_lookup(cooldown=timedelta(hours=24))

    assert vehicle_id in backlog


def test_backlog_excludes_vehicle_without_plate(pg_engine) -> None:
    repo = PostgresVehicleAmbientLabelRepository(pg_engine)
    vehicle_id = uuid4()
    _insert_vehicle(pg_engine, vehicle_id, license_plate=None)

    backlog = repo.get_vehicles_needing_lookup(cooldown=timedelta(hours=24))

    assert vehicle_id not in backlog


def test_backlog_permanently_excludes_found_status(pg_engine) -> None:
    repo = PostgresVehicleAmbientLabelRepository(pg_engine)
    vehicle_id = uuid4()
    _insert_vehicle(pg_engine, vehicle_id)
    # last_checked_at far in the past — would otherwise be past any cooldown
    repo.upsert(vehicle_id, AmbientLabel.A, AmbientLabelStatus.FOUND, datetime.now(UTC) - timedelta(days=365))

    backlog = repo.get_vehicles_needing_lookup(cooldown=timedelta(hours=24))

    assert vehicle_id not in backlog


def test_backlog_excludes_inconclusive_result_within_cooldown(pg_engine) -> None:
    repo = PostgresVehicleAmbientLabelRepository(pg_engine)
    vehicle_id = uuid4()
    _insert_vehicle(pg_engine, vehicle_id)
    repo.upsert(vehicle_id, None, AmbientLabelStatus.NOT_FOUND, datetime.now(UTC))

    backlog = repo.get_vehicles_needing_lookup(cooldown=timedelta(hours=24))

    assert vehicle_id not in backlog


def test_deleting_vehicle_cascades_to_ambient_label_row(pg_engine) -> None:
    repo = PostgresVehicleAmbientLabelRepository(pg_engine)
    vehicle_id = uuid4()
    _insert_vehicle(pg_engine, vehicle_id)
    repo.upsert(vehicle_id, AmbientLabel.B, AmbientLabelStatus.FOUND, datetime.now(UTC))

    with pg_engine.begin() as conn:
        conn.execute(text("DELETE FROM vehicles WHERE id = :id"), {"id": str(vehicle_id)})

    assert repo.get_by_vehicle_id(vehicle_id) is None


def test_backlog_includes_inconclusive_result_past_cooldown(pg_engine) -> None:
    repo = PostgresVehicleAmbientLabelRepository(pg_engine)
    vehicle_id = uuid4()
    _insert_vehicle(pg_engine, vehicle_id)
    repo.upsert(vehicle_id, None, AmbientLabelStatus.ERROR, datetime.now(UTC) - timedelta(hours=25))

    backlog = repo.get_vehicles_needing_lookup(cooldown=timedelta(hours=24))

    assert vehicle_id in backlog


# ---------------------------------------------------------------------------
# PostgresAmbientLabelIconRepository
# ---------------------------------------------------------------------------


def test_icon_cache_miss_returns_none(pg_engine) -> None:
    repo = PostgresAmbientLabelIconRepository(pg_engine)
    assert repo.get_by_label(AmbientLabel.B) is None


def test_icon_cache_round_trip(pg_engine) -> None:
    repo = PostgresAmbientLabelIconRepository(pg_engine)
    repo.save(AmbientLabel.B, b"fake-svg-bytes", "image/svg+xml")

    cached = repo.get_by_label(AmbientLabel.B)

    assert cached is not None
    assert cached.image_bytes == b"fake-svg-bytes"
    assert cached.content_type == "image/svg+xml"


def test_icon_cache_save_overwrites(pg_engine) -> None:
    repo = PostgresAmbientLabelIconRepository(pg_engine)
    repo.save(AmbientLabel.C, b"old-bytes", "image/svg+xml")
    repo.save(AmbientLabel.C, b"new-bytes", "image/svg+xml")

    cached = repo.get_by_label(AmbientLabel.C)

    assert cached is not None
    assert cached.image_bytes == b"new-bytes"
