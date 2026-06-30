"""
Integration tests for PostgresVehicleConfigRepository.

Requires POSTGRES_DSN environment variable and the cryptography package.
Skipped automatically if either is absent.
"""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

try:
    import cryptography  # noqa: F401

    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False

pytestmark = pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="cryptography package not installed")


@pytest.fixture()
def fernet_key() -> bytes:
    from cryptography.fernet import Fernet

    return Fernet.generate_key()


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
                CREATE TABLE IF NOT EXISTS vehicle_configs (
                    vehicle_id UUID PRIMARY KEY REFERENCES vehicles(id),
                    brand VARCHAR(20) NOT NULL,
                    encrypted_payload BYTEA,
                    location_token VARCHAR(64),
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
        )
        conn.execute(text("TRUNCATE vehicle_configs, vehicles, users CASCADE"))
    yield engine
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE vehicle_configs, vehicles, users CASCADE"))
    engine.dispose()


def _insert_vehicle(engine, vehicle_id, brand="generic") -> None:
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
                " VALUES (:id, :brand, 'Test', :now, :user_id)"
            ),
            {"id": str(vehicle_id), "brand": brand, "now": datetime.now(UTC), "user_id": str(user_id)},
        )


def test_toyota_config_is_stored_encrypted(pg_engine, fernet_key) -> None:
    from mobility_manager.domain.value_objects.toyota_config import ToyotaConfig
    from mobility_manager.infrastructure.repositories.postgres.vehicle_config_repo import (
        PostgresVehicleConfigRepository,
    )

    repo = PostgresVehicleConfigRepository(pg_engine, fernet_key)
    vehicle_id = uuid4()
    _insert_vehicle(pg_engine, vehicle_id, "toyota")

    config = ToyotaConfig(username="alice", password="s3cr3t", locale="en_GB", vin="VIN001")
    repo.save_toyota_config(vehicle_id, config)

    # Verify raw DB payload is ciphertext, not plaintext
    with pg_engine.connect() as conn:
        row = conn.execute(
            text("SELECT encrypted_payload FROM vehicle_configs WHERE vehicle_id = :id"),
            {"id": str(vehicle_id)},
        ).fetchone()
    assert row is not None
    assert b"s3cr3t" not in row[0]


def test_toyota_config_round_trip(pg_engine, fernet_key) -> None:
    from mobility_manager.domain.value_objects.toyota_config import ToyotaConfig
    from mobility_manager.infrastructure.repositories.postgres.vehicle_config_repo import (
        PostgresVehicleConfigRepository,
    )

    repo = PostgresVehicleConfigRepository(pg_engine, fernet_key)
    vehicle_id = uuid4()
    _insert_vehicle(pg_engine, vehicle_id, "toyota")

    config = ToyotaConfig(username="alice", password="s3cr3t", locale="en_GB", vin="VIN001")
    repo.save_toyota_config(vehicle_id, config)
    recovered = repo.get_toyota_config(vehicle_id)

    assert recovered.username == "alice"
    assert recovered.password == "s3cr3t"
    assert recovered.locale == "en_GB"
    assert recovered.vin == "VIN001"


def test_generic_token_stored_cleartext(pg_engine, fernet_key) -> None:
    from mobility_manager.domain.value_objects.generic_config import GenericConfig
    from mobility_manager.infrastructure.repositories.postgres.vehicle_config_repo import (
        PostgresVehicleConfigRepository,
    )

    repo = PostgresVehicleConfigRepository(pg_engine, fernet_key)
    vehicle_id = uuid4()
    _insert_vehicle(pg_engine, vehicle_id, "generic")
    token = str(uuid4())

    repo.save_generic_config(vehicle_id, GenericConfig(location_token=token))

    # Verify raw DB value is the token in plaintext
    with pg_engine.connect() as conn:
        row = conn.execute(
            text("SELECT location_token FROM vehicle_configs WHERE vehicle_id = :id"),
            {"id": str(vehicle_id)},
        ).fetchone()
    assert row is not None
    assert row[0] == token


def test_find_vehicle_by_token(pg_engine, fernet_key) -> None:
    from mobility_manager.domain.value_objects.generic_config import GenericConfig
    from mobility_manager.infrastructure.repositories.postgres.vehicle_config_repo import (
        PostgresVehicleConfigRepository,
    )

    repo = PostgresVehicleConfigRepository(pg_engine, fernet_key)
    vehicle_id = uuid4()
    _insert_vehicle(pg_engine, vehicle_id, "generic")
    token = str(uuid4())

    repo.save_generic_config(vehicle_id, GenericConfig(location_token=token))

    found_id = repo.find_vehicle_by_token(token)
    assert found_id == vehicle_id


def test_find_vehicle_by_unknown_token_returns_none(pg_engine, fernet_key) -> None:
    from mobility_manager.infrastructure.repositories.postgres.vehicle_config_repo import (
        PostgresVehicleConfigRepository,
    )

    repo = PostgresVehicleConfigRepository(pg_engine, fernet_key)
    assert repo.find_vehicle_by_token("nonexistent-token") is None
