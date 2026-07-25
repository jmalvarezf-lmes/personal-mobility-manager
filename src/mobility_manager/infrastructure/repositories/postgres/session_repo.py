"""
Infrastructure: PostgresSessionRepository.

SQLAlchemy Core implementation of the SessionRepository port.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, or_, select, update
from sqlalchemy.engine import Engine

from mobility_manager.domain.entities.session import Session
from mobility_manager.domain.ports.session_repository import SessionRepository
from mobility_manager.infrastructure.orm.tables import sessions_table


class PostgresSessionRepository(SessionRepository):
    """PostgreSQL-backed session repository using SQLAlchemy Core."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create(self, user_id: UUID, expires_at: datetime) -> Session:
        """Insert a new session row for user_id, expiring at expires_at."""
        new_id = uuid4()
        now = datetime.now(UTC)

        stmt = (
            sessions_table.insert()
            .values(
                id=new_id,
                user_id=user_id,
                created_at=now,
                expires_at=expires_at,
                revoked_at=None,
            )
            .returning(sessions_table)
        )

        with self._engine.begin() as conn:
            row = conn.execute(stmt).fetchone()

        assert row is not None
        return self._row_to_session(row)

    def find_by_id(self, session_id: UUID) -> Session | None:
        """Return the session with the given UUID, or None if not found."""
        with self._engine.connect() as conn:
            row = conn.execute(
                select(sessions_table).where(sessions_table.c.id == session_id)
            ).fetchone()

        if row is None:
            return None
        return self._row_to_session(row)

    def revoke(self, session_id: UUID) -> None:
        """Set revoked_at to now() on the session with the given UUID (no-op if missing)."""
        stmt = (
            update(sessions_table)
            .where(sessions_table.c.id == session_id)
            .values(revoked_at=datetime.now(UTC))
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def delete_older_than(self, cutoff: datetime) -> int:
        """Delete sessions whose revoked_at or expires_at predates cutoff. Returns rows deleted."""
        stmt = delete(sessions_table).where(
            or_(
                sessions_table.c.revoked_at < cutoff,
                sessions_table.c.expires_at < cutoff,
            )
        )
        with self._engine.begin() as conn:
            result = conn.execute(stmt)
            return result.rowcount

    @staticmethod
    def _row_to_session(row: object) -> Session:
        return Session(
            id=row.id,  # type: ignore[attr-defined]
            user_id=row.user_id,  # type: ignore[attr-defined]
            created_at=row.created_at,  # type: ignore[attr-defined]
            expires_at=row.expires_at,  # type: ignore[attr-defined]
            revoked_at=row.revoked_at,  # type: ignore[attr-defined]
        )
