"""
Integration tests for PostgresNotificationPreferencesRepository.

Requires POSTGRES_DSN environment variable. Skipped automatically if absent.

Also covers the migration/backfill verification (task 8.5): the raw-SQL
backfill statement used by the r5s6t7u8v9w0 Alembic revision is exercised
directly here against a real Postgres instance (same statement, run through
this fixture's schema) to confirm it produces exactly one disabled row per
existing user per catalog type and is idempotent on a second run.
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
                CREATE TABLE IF NOT EXISTS notification_types (
                    key TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    config_schema JSONB NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS user_notification_preferences (
                    user_id UUID NOT NULL REFERENCES users(id),
                    type_key TEXT NOT NULL REFERENCES notification_types(key),
                    enabled BOOLEAN NOT NULL,
                    config JSONB NOT NULL DEFAULT '{}',
                    updated_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (user_id, type_key)
                )
                """
            )
        )
        conn.execute(text("TRUNCATE user_notification_preferences, notification_types, users CASCADE"))
        conn.execute(
            text(
                """
                INSERT INTO notification_types (key, label, config_schema) VALUES
                    ('location_moved', 'Vehicle moved', '{"threshold_m": {"type": "integer", "min": 1}}'::jsonb),
                    ('ser_zone_ticket_required', 'SER ticket required',
                     '{"threshold_m": {"type": "integer", "min": 1}}'::jsonb)
                """
            )
        )
    yield engine
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE user_notification_preferences, notification_types, users CASCADE"))
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


def test_list_types_returns_seeded_catalog(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.notification_preferences_repo import (
        PostgresNotificationPreferencesRepository,
    )

    repo = PostgresNotificationPreferencesRepository(pg_engine)

    types = repo.list_types()

    keys = {t.key for t in types}
    assert keys == {"location_moved", "ser_zone_ticket_required"}
    for t in types:
        assert t.config_schema == {"threshold_m": {"type": "integer", "min": 1}}


def test_ensure_defaults_creates_disabled_rows_for_every_type(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.notification_preferences_repo import (
        PostgresNotificationPreferencesRepository,
    )

    repo = PostgresNotificationPreferencesRepository(pg_engine)
    user_id = _insert_user(pg_engine)

    repo.ensure_defaults(user_id)

    rows = repo.find_by_user_id(user_id)
    assert {r.type_key for r in rows} == {"location_moved", "ser_zone_ticket_required"}
    for row in rows:
        assert row.enabled is False
        assert row.config == {}


def test_ensure_defaults_only_inserts_missing_rows(pg_engine) -> None:
    """A type the user already has a (customized) row for is left untouched; only the missing type is backfilled."""
    from mobility_manager.infrastructure.repositories.postgres.notification_preferences_repo import (
        PostgresNotificationPreferencesRepository,
    )

    repo = PostgresNotificationPreferencesRepository(pg_engine)
    user_id = _insert_user(pg_engine)
    repo.update(user_id, "location_moved", enabled=True, config={"threshold_m": 20})

    repo.ensure_defaults(user_id)

    rows = {r.type_key: r for r in repo.find_by_user_id(user_id)}
    assert rows["location_moved"].enabled is True
    assert rows["location_moved"].config == {"threshold_m": 20}
    assert rows["ser_zone_ticket_required"].enabled is False
    assert rows["ser_zone_ticket_required"].config == {}


def test_ensure_defaults_is_idempotent(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.notification_preferences_repo import (
        PostgresNotificationPreferencesRepository,
    )

    repo = PostgresNotificationPreferencesRepository(pg_engine)
    user_id = _insert_user(pg_engine)

    repo.ensure_defaults(user_id)
    repo.ensure_defaults(user_id)

    rows = repo.find_by_user_id(user_id)
    assert len(rows) == 2  # not duplicated


def test_update_scopes_to_exactly_one_user_and_type(pg_engine) -> None:
    """update() must only change the targeted (user_id, type_key) row — every other row (same user, other type; other user, same type) stays untouched."""
    from mobility_manager.infrastructure.repositories.postgres.notification_preferences_repo import (
        PostgresNotificationPreferencesRepository,
    )

    repo = PostgresNotificationPreferencesRepository(pg_engine)
    user_a = _insert_user(pg_engine)
    user_b = _insert_user(pg_engine)
    repo.ensure_defaults(user_a)
    repo.ensure_defaults(user_b)

    repo.update(user_a, "location_moved", enabled=True, config={"threshold_m": 20})

    rows_a = {r.type_key: r for r in repo.find_by_user_id(user_a)}
    rows_b = {r.type_key: r for r in repo.find_by_user_id(user_b)}

    assert rows_a["location_moved"].enabled is True
    assert rows_a["location_moved"].config == {"threshold_m": 20}
    # Same user, other type — untouched.
    assert rows_a["ser_zone_ticket_required"].enabled is False
    assert rows_a["ser_zone_ticket_required"].config == {}
    # Other user, same type — untouched.
    assert rows_b["location_moved"].enabled is False
    assert rows_b["location_moved"].config == {}


def test_update_provisions_row_when_absent(pg_engine) -> None:
    """update() inserts the row first (ensure_defaults semantics) when it doesn't already exist."""
    from mobility_manager.infrastructure.repositories.postgres.notification_preferences_repo import (
        PostgresNotificationPreferencesRepository,
    )

    repo = PostgresNotificationPreferencesRepository(pg_engine)
    user_id = _insert_user(pg_engine)  # no ensure_defaults call

    updated = repo.update(user_id, "location_moved", enabled=True, config={"threshold_m": 30})

    assert updated.enabled is True
    assert updated.config == {"threshold_m": 30}
    rows = repo.find_by_user_id(user_id)
    assert len(rows) == 1


def test_find_by_user_id_returns_empty_list_when_no_rows(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.notification_preferences_repo import (
        PostgresNotificationPreferencesRepository,
    )

    repo = PostgresNotificationPreferencesRepository(pg_engine)
    assert repo.find_by_user_id(uuid4()) == []


def test_find_by_user_id_and_type_returns_matching_row(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.notification_preferences_repo import (
        PostgresNotificationPreferencesRepository,
    )

    repo = PostgresNotificationPreferencesRepository(pg_engine)
    user_id = _insert_user(pg_engine)
    repo.update(user_id, "location_moved", enabled=True, config={"threshold_m": 20})
    repo.update(user_id, "ser_zone_ticket_required", enabled=False, config={})

    row = repo.find_by_user_id_and_type(user_id, "location_moved")

    assert row is not None
    assert row.type_key == "location_moved"
    assert row.enabled is True
    assert row.config == {"threshold_m": 20}


def test_find_by_user_id_and_type_returns_none_when_row_absent(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.notification_preferences_repo import (
        PostgresNotificationPreferencesRepository,
    )

    repo = PostgresNotificationPreferencesRepository(pg_engine)
    user_id = _insert_user(pg_engine)

    assert repo.find_by_user_id_and_type(user_id, "location_moved") is None


def test_find_by_user_id_and_type_scopes_to_exactly_one_user(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.notification_preferences_repo import (
        PostgresNotificationPreferencesRepository,
    )

    repo = PostgresNotificationPreferencesRepository(pg_engine)
    user_a = _insert_user(pg_engine)
    user_b = _insert_user(pg_engine)
    repo.update(user_a, "location_moved", enabled=True, config={"threshold_m": 20})

    assert repo.find_by_user_id_and_type(user_b, "location_moved") is None


class TestMigrationBackfillVerification:
    """
    Exercises the same INSERT ... SELECT ... ON CONFLICT DO NOTHING
    statement used by alembic/versions/r5s6t7u8v9w0_backfill_user_notification_preferences.py
    directly against Postgres, verifying the scenarios from spec.md:
    "Backfill migration disables all types for all existing users" and
    "Backfill is idempotent".
    """

    _BACKFILL_SQL = """
        INSERT INTO user_notification_preferences (user_id, type_key, enabled, config, updated_at)
        SELECT users.id, notification_types.key, false, '{}'::jsonb, now()
        FROM users
        CROSS JOIN notification_types
        ON CONFLICT (user_id, type_key) DO NOTHING
    """

    def test_backfill_produces_one_disabled_row_per_user_per_type(self, pg_engine) -> None:
        user_a = _insert_user(pg_engine)
        user_b = _insert_user(pg_engine)

        with pg_engine.begin() as conn:
            conn.execute(text(self._BACKFILL_SQL))

        with pg_engine.connect() as conn:
            rows = conn.execute(text("SELECT user_id, type_key, enabled, config FROM user_notification_preferences"))
            rows = rows.fetchall()

        assert len(rows) == 4  # 2 users x 2 types
        by_user = {}
        for row in rows:
            by_user.setdefault(row.user_id, set()).add(row.type_key)
            assert row.enabled is False
            assert row.config == {}
        assert by_user[user_a] == {"location_moved", "ser_zone_ticket_required"}
        assert by_user[user_b] == {"location_moved", "ser_zone_ticket_required"}

    def test_backfill_is_idempotent(self, pg_engine) -> None:
        _insert_user(pg_engine)

        with pg_engine.begin() as conn:
            conn.execute(text(self._BACKFILL_SQL))
        with pg_engine.begin() as conn:
            conn.execute(text(self._BACKFILL_SQL))  # re-run

        with pg_engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM user_notification_preferences")).scalar_one()

        assert count == 2  # not duplicated

    def test_backfill_does_not_overwrite_a_customized_row(self, pg_engine) -> None:
        user_id = _insert_user(pg_engine)
        with pg_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO user_notification_preferences (user_id, type_key, enabled, config, updated_at)
                    VALUES (:user_id, 'location_moved', true, '{"threshold_m": 20}'::jsonb, now())
                    """
                ),
                {"user_id": str(user_id)},
            )

        with pg_engine.begin() as conn:
            conn.execute(text(self._BACKFILL_SQL))

        with pg_engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT enabled, config FROM user_notification_preferences"
                    " WHERE user_id = :user_id AND type_key = 'location_moved'"
                ),
                {"user_id": str(user_id)},
            ).fetchone()

        assert row.enabled is True
        assert row.config == {"threshold_m": 20}
