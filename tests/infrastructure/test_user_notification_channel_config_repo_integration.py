"""
Integration tests for PostgresUserNotificationChannelConfigRepository.

Requires POSTGRES_DSN environment variable. Skipped automatically if absent.
Unlike PostgresUserSerProviderConfigRepository's integration tests, this
repository has no encryption dependency — the stored `config` column is
plain JSON, confirmed directly by one of the tests below.
"""

import json
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
                CREATE TABLE IF NOT EXISTS user_notification_channel_configs (
                    user_id UUID NOT NULL REFERENCES users(id),
                    channel TEXT NOT NULL,
                    config TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (user_id, channel)
                )
                """
            )
        )
        conn.execute(text("TRUNCATE user_notification_channel_configs, users CASCADE"))
    yield engine
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE user_notification_channel_configs, users CASCADE"))
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


def test_save_then_find_round_trips_recipient(pg_engine) -> None:
    from mobility_manager.domain.value_objects.notification_recipient import (
        NotificationRecipient,
    )
    from mobility_manager.infrastructure.repositories.postgres.user_notification_channel_config_repo import (
        PostgresUserNotificationChannelConfigRepository,
    )

    repo = PostgresUserNotificationChannelConfigRepository(pg_engine)
    user_id = uuid4()
    _insert_user(pg_engine, user_id)

    recipient = NotificationRecipient(data={"chat_id": 123456789})
    repo.save(user_id, "telegram", recipient)

    recovered = repo.find(user_id, "telegram")
    assert recovered is not None
    assert recovered.data == recipient.data


def test_find_returns_none_when_absent(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.user_notification_channel_config_repo import (
        PostgresUserNotificationChannelConfigRepository,
    )

    repo = PostgresUserNotificationChannelConfigRepository(pg_engine)
    assert repo.find(uuid4(), "telegram") is None


def test_config_column_is_plain_readable_json_not_encrypted(pg_engine) -> None:
    from mobility_manager.domain.value_objects.notification_recipient import (
        NotificationRecipient,
    )
    from mobility_manager.infrastructure.repositories.postgres.user_notification_channel_config_repo import (
        PostgresUserNotificationChannelConfigRepository,
    )

    repo = PostgresUserNotificationChannelConfigRepository(pg_engine)
    user_id = uuid4()
    _insert_user(pg_engine, user_id)

    repo.save(user_id, "telegram", NotificationRecipient(data={"chat_id": 987654321}))

    with pg_engine.connect() as conn:
        row = conn.execute(
            text("SELECT config FROM user_notification_channel_configs WHERE user_id = :id"),
            {"id": str(user_id)},
        ).fetchone()
    assert row is not None
    # Plain, human-readable JSON — not Fernet ciphertext.
    assert json.loads(row.config) == {"chat_id": 987654321}


def test_find_all_by_user_id_reflects_stored_rows(pg_engine) -> None:
    from mobility_manager.domain.value_objects.notification_recipient import (
        NotificationRecipient,
    )
    from mobility_manager.infrastructure.repositories.postgres.user_notification_channel_config_repo import (
        PostgresUserNotificationChannelConfigRepository,
    )

    repo = PostgresUserNotificationChannelConfigRepository(pg_engine)
    user_id = uuid4()
    _insert_user(pg_engine, user_id)

    repo.save(user_id, "telegram", NotificationRecipient(data={"chat_id": 1}))

    result = repo.find_all_by_user_id(user_id)
    assert len(result) == 1
    channel, recipient = result[0]
    assert channel == "telegram"
    assert recipient.data == {"chat_id": 1}


def test_find_all_by_user_id_returns_empty_list_for_user_with_none(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.user_notification_channel_config_repo import (
        PostgresUserNotificationChannelConfigRepository,
    )

    repo = PostgresUserNotificationChannelConfigRepository(pg_engine)
    user_id = uuid4()
    _insert_user(pg_engine, user_id)

    assert repo.find_all_by_user_id(user_id) == []


def test_upsert_overwrites_existing_row_for_same_pair(pg_engine) -> None:
    from mobility_manager.domain.value_objects.notification_recipient import (
        NotificationRecipient,
    )
    from mobility_manager.infrastructure.repositories.postgres.user_notification_channel_config_repo import (
        PostgresUserNotificationChannelConfigRepository,
    )

    repo = PostgresUserNotificationChannelConfigRepository(pg_engine)
    user_id = uuid4()
    _insert_user(pg_engine, user_id)

    repo.save(user_id, "telegram", NotificationRecipient(data={"chat_id": 1}))
    repo.save(user_id, "telegram", NotificationRecipient(data={"chat_id": 2}))

    with pg_engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM user_notification_channel_configs WHERE user_id = :id AND channel = :channel"),
            {"id": str(user_id), "channel": "telegram"},
        ).scalar()
    assert count == 1

    recovered = repo.find(user_id, "telegram")
    assert recovered is not None
    assert recovered.data == {"chat_id": 2}


def test_delete_removes_existing_row(pg_engine) -> None:
    from mobility_manager.domain.value_objects.notification_recipient import (
        NotificationRecipient,
    )
    from mobility_manager.infrastructure.repositories.postgres.user_notification_channel_config_repo import (
        PostgresUserNotificationChannelConfigRepository,
    )

    repo = PostgresUserNotificationChannelConfigRepository(pg_engine)
    user_id = uuid4()
    _insert_user(pg_engine, user_id)

    repo.save(user_id, "telegram", NotificationRecipient(data={"chat_id": 1}))
    assert repo.find(user_id, "telegram") is not None

    repo.delete(user_id, "telegram")

    assert repo.find(user_id, "telegram") is None


def test_delete_is_idempotent_when_no_row_exists(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.user_notification_channel_config_repo import (
        PostgresUserNotificationChannelConfigRepository,
    )

    repo = PostgresUserNotificationChannelConfigRepository(pg_engine)
    user_id = uuid4()
    _insert_user(pg_engine, user_id)

    repo.delete(user_id, "telegram")  # should not raise
