"""
Integration tests for PostgresVehicleShareRepository.

Requires POSTGRES_DSN environment variable.
Skipped automatically when the variable is absent.
"""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from mobility_manager.domain.entities.vehicle_share import VehicleShare


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
                    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS vehicle_shares (
                    vehicle_id UUID NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (vehicle_id, user_id)
                )
                """
            )
        )
        conn.execute(text("TRUNCATE vehicle_shares, vehicles, users CASCADE"))
    yield engine
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE vehicle_shares, vehicles, users CASCADE"))
    engine.dispose()


def _insert_user(engine, user_id) -> None:  # type: ignore[no-untyped-def]
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, display_name, created_at)"
                " VALUES (:id, :sub, (:id || '@example.com'), 'Test User', :now)"
            ),
            {"id": str(user_id), "sub": str(uuid4()), "now": datetime.now(UTC)},
        )


def _insert_vehicle(engine, vehicle_id, user_id) -> None:  # type: ignore[no-untyped-def]
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO vehicles (id, brand, display_name, license_plate, created_at, owner_id)"
                " VALUES (:id, 'generic', 'Test Car', NULL, :now, :user_id)"
            ),
            {"id": str(vehicle_id), "now": datetime.now(UTC), "user_id": str(user_id)},
        )


def _make_repo(engine):  # type: ignore[no-untyped-def]
    from mobility_manager.infrastructure.repositories.postgres.vehicle_share_repo import (
        PostgresVehicleShareRepository,
    )

    return PostgresVehicleShareRepository(engine)


def test_save_persists_share(pg_engine) -> None:  # type: ignore[no-untyped-def]
    owner_id = uuid4()
    sharee_id = uuid4()
    vehicle_id = uuid4()
    _insert_user(pg_engine, owner_id)
    _insert_user(pg_engine, sharee_id)
    _insert_vehicle(pg_engine, vehicle_id, owner_id)

    repo = _make_repo(pg_engine)
    created_at = datetime.now(UTC)
    repo.save(
        VehicleShare(vehicle_id=vehicle_id, user_id=sharee_id, created_at=created_at)
    )

    row = repo.find_by_vehicle_and_user(vehicle_id, sharee_id)
    assert row is not None
    assert row.vehicle_id == vehicle_id
    assert row.user_id == sharee_id


def test_save_is_idempotent(pg_engine) -> None:  # type: ignore[no-untyped-def]
    owner_id = uuid4()
    sharee_id = uuid4()
    vehicle_id = uuid4()
    _insert_user(pg_engine, owner_id)
    _insert_user(pg_engine, sharee_id)
    _insert_vehicle(pg_engine, vehicle_id, owner_id)

    repo = _make_repo(pg_engine)
    share = VehicleShare(vehicle_id=vehicle_id, user_id=sharee_id, created_at=datetime.now(UTC))
    repo.save(share)
    repo.save(share)

    shares = repo.list_sharees(vehicle_id)
    assert len(shares) == 1


def test_find_by_vehicle_and_user_returns_none_when_absent(pg_engine) -> None:  # type: ignore[no-untyped-def]
    repo = _make_repo(pg_engine)
    assert repo.find_by_vehicle_and_user(uuid4(), uuid4()) is None


def test_list_sharees_returns_only_this_vehicles_shares(pg_engine) -> None:  # type: ignore[no-untyped-def]
    owner_id = uuid4()
    sharee_a = uuid4()
    sharee_b = uuid4()
    vehicle_a = uuid4()
    vehicle_b = uuid4()
    for user_id in (owner_id, sharee_a, sharee_b):
        _insert_user(pg_engine, user_id)
    _insert_vehicle(pg_engine, vehicle_a, owner_id)
    _insert_vehicle(pg_engine, vehicle_b, owner_id)

    repo = _make_repo(pg_engine)
    now = datetime.now(UTC)
    repo.save(VehicleShare(vehicle_id=vehicle_a, user_id=sharee_a, created_at=now))
    repo.save(VehicleShare(vehicle_id=vehicle_a, user_id=sharee_b, created_at=now))
    repo.save(VehicleShare(vehicle_id=vehicle_b, user_id=sharee_a, created_at=now))

    shares = repo.list_sharees(vehicle_a)
    sharee_ids = {s.user_id for s in shares}

    assert sharee_ids == {sharee_a, sharee_b}


def test_delete_removes_share(pg_engine) -> None:  # type: ignore[no-untyped-def]
    owner_id = uuid4()
    sharee_id = uuid4()
    vehicle_id = uuid4()
    _insert_user(pg_engine, owner_id)
    _insert_user(pg_engine, sharee_id)
    _insert_vehicle(pg_engine, vehicle_id, owner_id)

    repo = _make_repo(pg_engine)
    repo.save(
        VehicleShare(vehicle_id=vehicle_id, user_id=sharee_id, created_at=datetime.now(UTC))
    )
    repo.delete(vehicle_id, sharee_id)

    assert repo.find_by_vehicle_and_user(vehicle_id, sharee_id) is None


def test_delete_is_idempotent(pg_engine) -> None:  # type: ignore[no-untyped-def]
    repo = _make_repo(pg_engine)
    repo.delete(uuid4(), uuid4())


def test_list_vehicle_ids_for_user_returns_shared_vehicles(pg_engine) -> None:  # type: ignore[no-untyped-def]
    owner_id = uuid4()
    sharee_id = uuid4()
    other_user_id = uuid4()
    vehicle_a = uuid4()
    vehicle_b = uuid4()
    for user_id in (owner_id, sharee_id, other_user_id):
        _insert_user(pg_engine, user_id)
    _insert_vehicle(pg_engine, vehicle_a, owner_id)
    _insert_vehicle(pg_engine, vehicle_b, owner_id)

    repo = _make_repo(pg_engine)
    now = datetime.now(UTC)
    repo.save(VehicleShare(vehicle_id=vehicle_a, user_id=sharee_id, created_at=now))
    repo.save(VehicleShare(vehicle_id=vehicle_b, user_id=other_user_id, created_at=now))

    ids = repo.list_vehicle_ids_for_user(sharee_id)

    assert ids == [vehicle_a]


def test_cascade_delete_when_vehicle_removed(pg_engine) -> None:  # type: ignore[no-untyped-def]
    owner_id = uuid4()
    sharee_id = uuid4()
    vehicle_id = uuid4()
    _insert_user(pg_engine, owner_id)
    _insert_user(pg_engine, sharee_id)
    _insert_vehicle(pg_engine, vehicle_id, owner_id)

    repo = _make_repo(pg_engine)
    repo.save(
        VehicleShare(vehicle_id=vehicle_id, user_id=sharee_id, created_at=datetime.now(UTC))
    )

    with pg_engine.begin() as conn:
        conn.execute(text("DELETE FROM vehicles WHERE id = :id"), {"id": str(vehicle_id)})

    assert repo.find_by_vehicle_and_user(vehicle_id, sharee_id) is None
