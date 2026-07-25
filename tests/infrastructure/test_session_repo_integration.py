"""
Integration tests for PostgresSessionRepository.

Requires POSTGRES_DSN environment variable. Skipped automatically if absent,
mirroring tests/infrastructure/test_user_preferences_repo_integration.py.
"""

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from mobility_manager.infrastructure.repositories.postgres.session_repo import (
    PostgresSessionRepository,
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
                CREATE TABLE IF NOT EXISTS sessions (
                    id UUID PRIMARY KEY,
                    user_id UUID NOT NULL REFERENCES users(id),
                    created_at TIMESTAMPTZ NOT NULL,
                    expires_at TIMESTAMPTZ NOT NULL,
                    revoked_at TIMESTAMPTZ NULL
                )
                """
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions (user_id)"))
        conn.execute(text("TRUNCATE sessions, users CASCADE"))
    yield engine
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE sessions, users CASCADE"))
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


class TestCreateAndFindById:
    def test_create_persists_a_row_and_find_by_id_returns_matching_fields(self, pg_engine) -> None:
        repo = PostgresSessionRepository(pg_engine)
        user_id = _insert_user(pg_engine)
        expires_at = datetime.now(UTC) + timedelta(hours=24)

        session = repo.create(user_id=user_id, expires_at=expires_at)

        found = repo.find_by_id(session.id)
        assert found is not None
        assert found.id == session.id
        assert found.user_id == user_id
        assert found.revoked_at is None
        assert abs((found.expires_at - expires_at).total_seconds()) < 1

    def test_find_by_id_returns_none_when_missing(self, pg_engine) -> None:
        repo = PostgresSessionRepository(pg_engine)
        assert repo.find_by_id(uuid4()) is None


class TestRevoke:
    def test_revoke_sets_revoked_at_and_leaves_row_present(self, pg_engine) -> None:
        repo = PostgresSessionRepository(pg_engine)
        user_id = _insert_user(pg_engine)
        session = repo.create(user_id=user_id, expires_at=datetime.now(UTC) + timedelta(hours=24))

        repo.revoke(session.id)

        found = repo.find_by_id(session.id)
        assert found is not None
        assert found.revoked_at is not None

    def test_revoke_is_noop_for_unknown_session(self, pg_engine) -> None:
        repo = PostgresSessionRepository(pg_engine)
        # Must not raise.
        repo.revoke(uuid4())


class TestDeleteOlderThan:
    def test_deletes_rows_predating_cutoff_and_leaves_newer_rows(self, pg_engine) -> None:
        repo = PostgresSessionRepository(pg_engine)
        user_id = _insert_user(pg_engine)
        now = datetime.now(UTC)

        old_expired = repo.create(user_id=user_id, expires_at=now - timedelta(days=40))
        old_revoked = repo.create(user_id=user_id, expires_at=now + timedelta(hours=1))
        repo.revoke(old_revoked.id)
        # Backdate revoked_at directly (revoke() always sets "now").
        with pg_engine.begin() as conn:
            conn.execute(
                text("UPDATE sessions SET revoked_at = :revoked_at WHERE id = :id"),
                {"revoked_at": now - timedelta(days=40), "id": str(old_revoked.id)},
            )
        recent = repo.create(user_id=user_id, expires_at=now + timedelta(hours=24))

        cutoff = now - timedelta(days=30)
        deleted_count = repo.delete_older_than(cutoff)

        assert deleted_count == 2
        assert repo.find_by_id(old_expired.id) is None
        assert repo.find_by_id(old_revoked.id) is None
        assert repo.find_by_id(recent.id) is not None


class TestForeignKeyConstraint:
    def test_create_with_unknown_user_id_raises_integrity_error(self, pg_engine) -> None:
        repo = PostgresSessionRepository(pg_engine)
        with pytest.raises(IntegrityError):
            repo.create(user_id=uuid4(), expires_at=datetime.now(UTC) + timedelta(hours=24))
