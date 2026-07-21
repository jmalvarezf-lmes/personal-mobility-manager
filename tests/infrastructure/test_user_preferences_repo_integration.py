"""
Integration tests for PostgresUserPreferencesRepository.

Requires POSTGRES_DSN environment variable. Skipped automatically if absent.
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
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id UUID PRIMARY KEY REFERENCES users(id),
                    default_ticket_duration_minutes INT NOT NULL DEFAULT 60,
                    auto_create_ticket BOOLEAN NOT NULL DEFAULT false,
                    preferred_notification_channel TEXT NULL,
                    notification_language TEXT NULL,
                    timezone TEXT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
        )
        conn.execute(text("TRUNCATE user_preferences, users CASCADE"))
    yield engine
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE user_preferences, users CASCADE"))
    engine.dispose()


def _insert_user(engine) -> object:
    user_id = uuid4()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, display_name, created_at)"
                " VALUES (:id, :sub, 'test@example.com', 'Test User', :now)"
            ),
            {"id": str(user_id), "sub": str(uuid4()), "now": datetime.now(UTC)},
        )
    return user_id


def test_ensure_default_creates_row_with_defaults(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.user_preferences_repo import (
        PostgresUserPreferencesRepository,
    )

    repo = PostgresUserPreferencesRepository(pg_engine)
    user_id = _insert_user(pg_engine)

    repo.ensure_default(user_id)

    preferences = repo.find_by_user_id(user_id)
    assert preferences is not None
    assert preferences.default_ticket_duration_minutes == 60
    assert preferences.auto_create_ticket is False
    assert preferences.preferred_notification_channel is None
    assert preferences.notification_language is None
    assert preferences.timezone is None


def test_ensure_default_is_noop_for_existing_row(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.user_preferences_repo import (
        PostgresUserPreferencesRepository,
    )

    repo = PostgresUserPreferencesRepository(pg_engine)
    user_id = _insert_user(pg_engine)

    repo.ensure_default(user_id)
    repo.update(
        user_id,
        default_ticket_duration_minutes=90,
        auto_create_ticket=True,
        preferred_notification_channel="telegram",
        notification_language="es",
        timezone="Europe/Madrid",
    )

    # Calling ensure_default again must not touch the now-customized row.
    repo.ensure_default(user_id)

    preferences = repo.find_by_user_id(user_id)
    assert preferences is not None
    assert preferences.default_ticket_duration_minutes == 90
    assert preferences.auto_create_ticket is True
    assert preferences.preferred_notification_channel == "telegram"
    assert preferences.notification_language == "es"
    assert preferences.timezone == "Europe/Madrid"


def test_find_by_user_id_returns_none_when_missing(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.user_preferences_repo import (
        PostgresUserPreferencesRepository,
    )

    repo = PostgresUserPreferencesRepository(pg_engine)
    assert repo.find_by_user_id(uuid4()) is None


def test_update_overwrites_values_and_updated_at(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.user_preferences_repo import (
        PostgresUserPreferencesRepository,
    )

    repo = PostgresUserPreferencesRepository(pg_engine)
    user_id = _insert_user(pg_engine)
    repo.ensure_default(user_id)
    original = repo.find_by_user_id(user_id)
    assert original is not None

    updated = repo.update(
        user_id,
        default_ticket_duration_minutes=120,
        auto_create_ticket=True,
        preferred_notification_channel="telegram",
        notification_language="es",
        timezone="Europe/Madrid",
    )

    assert updated.default_ticket_duration_minutes == 120
    assert updated.auto_create_ticket is True
    assert updated.preferred_notification_channel == "telegram"
    assert updated.notification_language == "es"
    assert updated.timezone == "Europe/Madrid"
    assert updated.updated_at >= original.updated_at

    refetched = repo.find_by_user_id(user_id)
    assert refetched is not None
    assert refetched.default_ticket_duration_minutes == 120
    assert refetched.auto_create_ticket is True
    assert refetched.preferred_notification_channel == "telegram"
    assert refetched.notification_language == "es"
    assert refetched.timezone == "Europe/Madrid"


def test_set_preferred_notification_channel_updates_only_that_field(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.user_preferences_repo import (
        PostgresUserPreferencesRepository,
    )

    repo = PostgresUserPreferencesRepository(pg_engine)
    user_id = _insert_user(pg_engine)
    repo.ensure_default(user_id)
    repo.update(
        user_id,
        default_ticket_duration_minutes=90,
        auto_create_ticket=True,
        preferred_notification_channel=None,
        notification_language=None,
        timezone=None,
    )

    repo.set_preferred_notification_channel(user_id, "telegram")

    preferences = repo.find_by_user_id(user_id)
    assert preferences is not None
    assert preferences.preferred_notification_channel == "telegram"
    assert preferences.default_ticket_duration_minutes == 90
    assert preferences.auto_create_ticket is True


def test_set_preferred_notification_channel_accepts_none_to_clear(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.user_preferences_repo import (
        PostgresUserPreferencesRepository,
    )

    repo = PostgresUserPreferencesRepository(pg_engine)
    user_id = _insert_user(pg_engine)
    repo.ensure_default(user_id)
    repo.update(
        user_id,
        default_ticket_duration_minutes=60,
        auto_create_ticket=False,
        preferred_notification_channel="telegram",
        notification_language=None,
        timezone=None,
    )

    repo.set_preferred_notification_channel(user_id, None)

    preferences = repo.find_by_user_id(user_id)
    assert preferences is not None
    assert preferences.preferred_notification_channel is None


def test_set_preferred_notification_channel_leaves_notification_language_untouched(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.user_preferences_repo import (
        PostgresUserPreferencesRepository,
    )

    repo = PostgresUserPreferencesRepository(pg_engine)
    user_id = _insert_user(pg_engine)
    repo.ensure_default(user_id)
    repo.update(
        user_id,
        default_ticket_duration_minutes=60,
        auto_create_ticket=False,
        preferred_notification_channel=None,
        notification_language="es",
        timezone=None,
    )

    repo.set_preferred_notification_channel(user_id, "telegram")

    preferences = repo.find_by_user_id(user_id)
    assert preferences is not None
    assert preferences.preferred_notification_channel == "telegram"
    assert preferences.notification_language == "es"


def test_update_can_clear_notification_language(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.user_preferences_repo import (
        PostgresUserPreferencesRepository,
    )

    repo = PostgresUserPreferencesRepository(pg_engine)
    user_id = _insert_user(pg_engine)
    repo.ensure_default(user_id)
    repo.update(
        user_id,
        default_ticket_duration_minutes=60,
        auto_create_ticket=False,
        preferred_notification_channel=None,
        notification_language="es",
        timezone=None,
    )

    updated = repo.update(
        user_id,
        default_ticket_duration_minutes=60,
        auto_create_ticket=False,
        preferred_notification_channel=None,
        notification_language=None,
        timezone=None,
    )

    assert updated.notification_language is None


def test_update_persists_timezone(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.user_preferences_repo import (
        PostgresUserPreferencesRepository,
    )

    repo = PostgresUserPreferencesRepository(pg_engine)
    user_id = _insert_user(pg_engine)
    repo.ensure_default(user_id)

    updated = repo.update(
        user_id,
        default_ticket_duration_minutes=60,
        auto_create_ticket=False,
        preferred_notification_channel=None,
        notification_language=None,
        timezone="Europe/Madrid",
    )

    assert updated.timezone == "Europe/Madrid"

    refetched = repo.find_by_user_id(user_id)
    assert refetched is not None
    assert refetched.timezone == "Europe/Madrid"


def test_update_can_clear_timezone(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.user_preferences_repo import (
        PostgresUserPreferencesRepository,
    )

    repo = PostgresUserPreferencesRepository(pg_engine)
    user_id = _insert_user(pg_engine)
    repo.ensure_default(user_id)
    repo.update(
        user_id,
        default_ticket_duration_minutes=60,
        auto_create_ticket=False,
        preferred_notification_channel=None,
        notification_language=None,
        timezone="Europe/Madrid",
    )

    updated = repo.update(
        user_id,
        default_ticket_duration_minutes=60,
        auto_create_ticket=False,
        preferred_notification_channel=None,
        notification_language=None,
        timezone=None,
    )

    assert updated.timezone is None

    refetched = repo.find_by_user_id(user_id)
    assert refetched is not None
    assert refetched.timezone is None
