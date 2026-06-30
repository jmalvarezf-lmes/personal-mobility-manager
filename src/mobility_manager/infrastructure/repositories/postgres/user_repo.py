"""
Infrastructure: PostgresUserRepository.

SQLAlchemy Core implementation of the UserRepository port.
Uses INSERT ... ON CONFLICT (google_sub) DO UPDATE for upsert semantics.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from mobility_manager.domain.entities.user import User
from mobility_manager.domain.ports.user_repository import UserRepository
from mobility_manager.infrastructure.orm.tables import users_table


class PostgresUserRepository(UserRepository):
    """PostgreSQL-backed user repository using SQLAlchemy Core."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def upsert(self, google_sub: str, email: str, display_name: str) -> User:
        """
        Insert or update a user identified by google_sub.

        Uses INSERT ... ON CONFLICT (google_sub) DO UPDATE to atomically
        provision new users and keep email/display_name current.
        """
        new_id = uuid4()
        now = datetime.now(UTC)

        stmt = (
            insert(users_table)
            .values(
                id=new_id,
                google_sub=google_sub,
                email=email,
                display_name=display_name,
                created_at=now,
            )
            .on_conflict_do_update(
                index_elements=["google_sub"],
                set_={"email": email, "display_name": display_name},
            )
            .returning(users_table)
        )

        with self._engine.begin() as conn:
            row = conn.execute(stmt).fetchone()

        assert row is not None
        return self._row_to_user(row)

    def find_by_id(self, user_id: UUID) -> User | None:
        """Return the user with the given UUID, or None if not found."""
        with self._engine.connect() as conn:
            row = conn.execute(
                select(users_table).where(users_table.c.id == user_id)
            ).fetchone()

        if row is None:
            return None
        return self._row_to_user(row)

    @staticmethod
    def _row_to_user(row: object) -> User:
        return User(
            id=row.id,  # type: ignore[attr-defined]
            google_sub=row.google_sub,  # type: ignore[attr-defined]
            email=row.email,  # type: ignore[attr-defined]
            display_name=row.display_name,  # type: ignore[attr-defined]
            created_at=row.created_at,  # type: ignore[attr-defined]
        )
