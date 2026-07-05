"""
Integration tests for PostgresUserSerProviderConfigRepository.

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
                CREATE TABLE IF NOT EXISTS user_ser_provider_configs (
                    user_id UUID NOT NULL REFERENCES users(id),
                    provider TEXT NOT NULL,
                    encrypted_payload BYTEA NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (user_id, provider)
                )
                """
            )
        )
        conn.execute(text("TRUNCATE user_ser_provider_configs, users CASCADE"))
    yield engine
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE user_ser_provider_configs, users CASCADE"))
    engine.dispose()


def _insert_user(engine, user_id) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, display_name, created_at)"
                " VALUES (:id, :sub, 'test@example.com', 'Test User', :now)"
            ),
            {"id": str(user_id), "sub": str(uuid4()), "now": datetime.now(UTC)},
        )


def test_save_then_find_round_trips_session(pg_engine, fernet_key) -> None:
    from mobility_manager.domain.value_objects.ser_provider_session import (
        SerProviderSession,
    )
    from mobility_manager.infrastructure.repositories.postgres.user_ser_provider_config_repo import (
        PostgresUserSerProviderConfigRepository,
    )

    repo = PostgresUserSerProviderConfigRepository(pg_engine, fernet_key)
    user_id = uuid4()
    _insert_user(pg_engine, user_id)

    session = SerProviderSession(data={"token": "abc123", "expires_in": 3600})
    repo.save(user_id, "madrid_ser_app", session)

    recovered = repo.find(user_id, "madrid_ser_app")
    assert recovered is not None
    assert recovered.data == session.data


def test_find_returns_none_when_absent(pg_engine, fernet_key) -> None:
    from mobility_manager.infrastructure.repositories.postgres.user_ser_provider_config_repo import (
        PostgresUserSerProviderConfigRepository,
    )

    repo = PostgresUserSerProviderConfigRepository(pg_engine, fernet_key)
    assert repo.find(uuid4(), "madrid_ser_app") is None


def test_save_stores_encrypted_payload_not_plaintext(pg_engine, fernet_key) -> None:
    from mobility_manager.domain.value_objects.ser_provider_session import (
        SerProviderSession,
    )
    from mobility_manager.infrastructure.repositories.postgres.user_ser_provider_config_repo import (
        PostgresUserSerProviderConfigRepository,
    )

    repo = PostgresUserSerProviderConfigRepository(pg_engine, fernet_key)
    user_id = uuid4()
    _insert_user(pg_engine, user_id)

    repo.save(user_id, "madrid_ser_app", SerProviderSession(data={"token": "s3cr3t-token"}))

    with pg_engine.connect() as conn:
        row = conn.execute(
            text("SELECT encrypted_payload FROM user_ser_provider_configs WHERE user_id = :id"),
            {"id": str(user_id)},
        ).fetchone()
    assert row is not None
    assert b"s3cr3t-token" not in row[0]


def test_upsert_overwrites_existing_row_for_same_pair(pg_engine, fernet_key) -> None:
    from mobility_manager.domain.value_objects.ser_provider_session import (
        SerProviderSession,
    )
    from mobility_manager.infrastructure.repositories.postgres.user_ser_provider_config_repo import (
        PostgresUserSerProviderConfigRepository,
    )

    repo = PostgresUserSerProviderConfigRepository(pg_engine, fernet_key)
    user_id = uuid4()
    _insert_user(pg_engine, user_id)

    repo.save(user_id, "madrid_ser_app", SerProviderSession(data={"token": "first"}))
    repo.save(user_id, "madrid_ser_app", SerProviderSession(data={"token": "second"}))

    with pg_engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM user_ser_provider_configs WHERE user_id = :id AND provider = :provider"),
            {"id": str(user_id), "provider": "madrid_ser_app"},
        ).scalar()
    assert count == 1

    recovered = repo.find(user_id, "madrid_ser_app")
    assert recovered is not None
    assert recovered.data == {"token": "second"}


def test_delete_removes_existing_row(pg_engine, fernet_key) -> None:
    from mobility_manager.domain.value_objects.ser_provider_session import (
        SerProviderSession,
    )
    from mobility_manager.infrastructure.repositories.postgres.user_ser_provider_config_repo import (
        PostgresUserSerProviderConfigRepository,
    )

    repo = PostgresUserSerProviderConfigRepository(pg_engine, fernet_key)
    user_id = uuid4()
    _insert_user(pg_engine, user_id)

    repo.save(user_id, "madrid_ser_app", SerProviderSession(data={"token": "abc"}))
    assert repo.find(user_id, "madrid_ser_app") is not None

    repo.delete(user_id, "madrid_ser_app")

    assert repo.find(user_id, "madrid_ser_app") is None


def test_delete_is_idempotent_when_no_row_exists(pg_engine, fernet_key) -> None:
    from mobility_manager.infrastructure.repositories.postgres.user_ser_provider_config_repo import (
        PostgresUserSerProviderConfigRepository,
    )

    repo = PostgresUserSerProviderConfigRepository(pg_engine, fernet_key)
    user_id = uuid4()
    _insert_user(pg_engine, user_id)

    repo.delete(user_id, "madrid_ser_app")  # should not raise


def test_list_connected_providers_reflects_stored_rows(pg_engine, fernet_key) -> None:
    from mobility_manager.domain.value_objects.ser_provider_session import (
        SerProviderSession,
    )
    from mobility_manager.infrastructure.repositories.postgres.user_ser_provider_config_repo import (
        PostgresUserSerProviderConfigRepository,
    )

    repo = PostgresUserSerProviderConfigRepository(pg_engine, fernet_key)
    user_id = uuid4()
    _insert_user(pg_engine, user_id)

    repo.save(user_id, "elparking", SerProviderSession(data={"token": "abc"}))

    assert repo.list_connected_providers(user_id) == ["elparking"]


def test_list_connected_providers_returns_empty_for_user_with_no_connections(pg_engine, fernet_key) -> None:
    from mobility_manager.infrastructure.repositories.postgres.user_ser_provider_config_repo import (
        PostgresUserSerProviderConfigRepository,
    )

    repo = PostgresUserSerProviderConfigRepository(pg_engine, fernet_key)
    user_id = uuid4()
    _insert_user(pg_engine, user_id)

    assert repo.list_connected_providers(user_id) == []
