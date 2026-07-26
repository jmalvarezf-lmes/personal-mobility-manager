"""
Integration tests for the two new data migrations introduced by
add-ser-ticket-auto-creation:

- 20c831d6fd2b (backfill ser_ticket_created / ser_ticket_creation_failed
  preference rows for every existing user)
- a5071149d885 (retroactive cascade: for every user already
  `auto_create_ticket=true`, force the two new types enabled and
  ser_zone_ticket_required disabled)

Requires POSTGRES_DSN. Skipped automatically if absent. Exercises the same
raw SQL statements the Alembic revisions run, directly against Postgres, per
task 1.4.
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
                    default_ticket_duration_minutes INTEGER NOT NULL DEFAULT 60,
                    auto_create_ticket BOOLEAN NOT NULL DEFAULT false,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
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
        conn.execute(
            text("TRUNCATE user_notification_preferences, user_preferences, notification_types, users CASCADE")
        )
        conn.execute(
            text(
                """
                INSERT INTO notification_types (key, label, config_schema) VALUES
                    ('ser_zone_ticket_required', 'SER ticket required',
                     '{"threshold_m": {"type": "integer", "min": 1}}'::jsonb),
                    ('ser_ticket_created', 'SER ticket created', '{}'::jsonb),
                    ('ser_ticket_creation_failed', 'SER ticket creation failed', '{}'::jsonb)
                """
            )
        )
    yield engine
    with engine.begin() as conn:
        conn.execute(
            text("TRUNCATE user_notification_preferences, user_preferences, notification_types, users CASCADE")
        )
    engine.dispose()


def _insert_user(engine, auto_create_ticket: bool = False) -> object:
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
            text("INSERT INTO user_preferences (user_id, auto_create_ticket, updated_at) VALUES (:id, :auto, :now)"),
            {"id": str(user_id), "auto": auto_create_ticket, "now": datetime.now(UTC)},
        )
    return user_id


_BACKFILL_SQL = """
    INSERT INTO user_notification_preferences (user_id, type_key, enabled, config, updated_at)
    SELECT users.id, notification_types.key, false, '{}'::jsonb, now()
    FROM users
    CROSS JOIN notification_types
    WHERE notification_types.key IN ('ser_ticket_created', 'ser_ticket_creation_failed')
    ON CONFLICT (user_id, type_key) DO NOTHING
"""

_RETROACTIVE_CASCADE_ENABLE_SQL = """
    UPDATE user_notification_preferences
    SET enabled = true, updated_at = now()
    WHERE type_key IN ('ser_ticket_created', 'ser_ticket_creation_failed')
      AND user_id IN (SELECT user_id FROM user_preferences WHERE auto_create_ticket = true)
"""

_RETROACTIVE_CASCADE_DISABLE_SQL = """
    UPDATE user_notification_preferences
    SET enabled = false, updated_at = now()
    WHERE type_key = 'ser_zone_ticket_required'
      AND user_id IN (SELECT user_id FROM user_preferences WHERE auto_create_ticket = true)
"""


class TestBackfillMigration:
    def test_backfill_produces_disabled_rows_for_the_two_new_types(self, pg_engine) -> None:
        user_id = _insert_user(pg_engine)

        with pg_engine.begin() as conn:
            conn.execute(text(_BACKFILL_SQL))

        with pg_engine.connect() as conn:
            rows = conn.execute(
                text("SELECT type_key, enabled, config FROM user_notification_preferences WHERE user_id = :id"),
                {"id": str(user_id)},
            ).fetchall()

        by_type = {row.type_key: row for row in rows}
        assert set(by_type) == {"ser_ticket_created", "ser_ticket_creation_failed"}
        for row in by_type.values():
            assert row.enabled is False
            assert row.config == {}

    def test_backfill_is_idempotent(self, pg_engine) -> None:
        _insert_user(pg_engine)

        with pg_engine.begin() as conn:
            conn.execute(text(_BACKFILL_SQL))
        with pg_engine.begin() as conn:
            conn.execute(text(_BACKFILL_SQL))  # re-run

        with pg_engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM user_notification_preferences")).scalar_one()

        assert count == 2  # not duplicated


class TestRetroactiveCascadeMigration:
    def test_cascade_enables_new_types_and_disables_zone_required_for_auto_create_users(self, pg_engine) -> None:
        auto_user = _insert_user(pg_engine, auto_create_ticket=True)
        manual_user = _insert_user(pg_engine, auto_create_ticket=False)
        with pg_engine.begin() as conn:
            conn.execute(text(_BACKFILL_SQL))
            for user_id in (auto_user, manual_user):
                conn.execute(
                    text(
                        "INSERT INTO user_notification_preferences (user_id, type_key, enabled, config, updated_at)"
                        " VALUES (:id, 'ser_zone_ticket_required', true, '{}'::jsonb, now())"
                    ),
                    {"id": str(user_id)},
                )

        with pg_engine.begin() as conn:
            conn.execute(text(_RETROACTIVE_CASCADE_ENABLE_SQL))
            conn.execute(text(_RETROACTIVE_CASCADE_DISABLE_SQL))

        with pg_engine.connect() as conn:
            auto_rows = {
                row.type_key: row.enabled
                for row in conn.execute(
                    text("SELECT type_key, enabled FROM user_notification_preferences WHERE user_id = :id"),
                    {"id": str(auto_user)},
                ).fetchall()
            }
            manual_rows = {
                row.type_key: row.enabled
                for row in conn.execute(
                    text("SELECT type_key, enabled FROM user_notification_preferences WHERE user_id = :id"),
                    {"id": str(manual_user)},
                ).fetchall()
            }

        assert auto_rows["ser_ticket_created"] is True
        assert auto_rows["ser_ticket_creation_failed"] is True
        assert auto_rows["ser_zone_ticket_required"] is False
        # A manual (non-auto-create) user's rows must be untouched by the cascade.
        assert manual_rows["ser_ticket_created"] is False
        assert manual_rows["ser_ticket_creation_failed"] is False
        assert manual_rows["ser_zone_ticket_required"] is True

    def test_cascade_is_idempotent(self, pg_engine) -> None:
        auto_user = _insert_user(pg_engine, auto_create_ticket=True)
        with pg_engine.begin() as conn:
            conn.execute(text(_BACKFILL_SQL))
            conn.execute(
                text(
                    "INSERT INTO user_notification_preferences (user_id, type_key, enabled, config, updated_at)"
                    " VALUES (:id, 'ser_zone_ticket_required', true, '{}'::jsonb, now())"
                ),
                {"id": str(auto_user)},
            )

        for _ in range(2):
            with pg_engine.begin() as conn:
                conn.execute(text(_RETROACTIVE_CASCADE_ENABLE_SQL))
                conn.execute(text(_RETROACTIVE_CASCADE_DISABLE_SQL))

        with pg_engine.connect() as conn:
            rows = {
                row.type_key: row.enabled
                for row in conn.execute(
                    text("SELECT type_key, enabled FROM user_notification_preferences WHERE user_id = :id"),
                    {"id": str(auto_user)},
                ).fetchall()
            }

        assert rows["ser_ticket_created"] is True
        assert rows["ser_ticket_creation_failed"] is True
        assert rows["ser_zone_ticket_required"] is False
