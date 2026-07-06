"""
Infrastructure: PostgresUserPreferencesRepository.

SQLAlchemy Core implementation of the UserPreferencesRepository port.
Uses INSERT ... ON CONFLICT (user_id) DO NOTHING for default-row provisioning.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from mobility_manager.domain.entities.user_preferences import UserPreferences
from mobility_manager.domain.ports.user_preferences_repository import (
    UserPreferencesRepository,
)
from mobility_manager.infrastructure.orm.tables import user_preferences_table

_DEFAULT_TICKET_DURATION_MINUTES = 60
_DEFAULT_AUTO_CREATE_TICKET = False


class PostgresUserPreferencesRepository(UserPreferencesRepository):
    """PostgreSQL-backed user preferences repository using SQLAlchemy Core."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def ensure_default(self, user_id: UUID) -> None:
        """
        Insert a default preferences row for user_id if one does not already exist.

        Uses INSERT ... ON CONFLICT (user_id) DO NOTHING so an existing row
        (and its values) is never touched.
        """
        now = datetime.now(UTC)
        stmt = (
            insert(user_preferences_table)
            .values(
                user_id=user_id,
                default_ticket_duration_minutes=_DEFAULT_TICKET_DURATION_MINUTES,
                auto_create_ticket=_DEFAULT_AUTO_CREATE_TICKET,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["user_id"])
        )

        with self._engine.begin() as conn:
            conn.execute(stmt)

    def find_by_user_id(self, user_id: UUID) -> UserPreferences | None:
        """Return the preferences for the given user, or None if none exist."""
        with self._engine.connect() as conn:
            row = conn.execute(
                select(user_preferences_table).where(user_preferences_table.c.user_id == user_id)
            ).fetchone()

        if row is None:
            return None
        return self._row_to_user_preferences(row)

    def update(
        self,
        user_id: UUID,
        default_ticket_duration_minutes: int,
        auto_create_ticket: bool,
        preferred_notification_channel: str | None,
        notification_language: str | None,
    ) -> UserPreferences:
        """Replace all four fields for the user's existing row and return the persisted UserPreferences."""
        now = datetime.now(UTC)
        stmt = (
            user_preferences_table.update()
            .where(user_preferences_table.c.user_id == user_id)
            .values(
                default_ticket_duration_minutes=default_ticket_duration_minutes,
                auto_create_ticket=auto_create_ticket,
                preferred_notification_channel=preferred_notification_channel,
                notification_language=notification_language,
                updated_at=now,
            )
            .returning(user_preferences_table)
        )

        with self._engine.begin() as conn:
            row = conn.execute(stmt).fetchone()

        assert row is not None
        return self._row_to_user_preferences(row)

    def set_preferred_notification_channel(self, user_id: UUID, channel: str | None) -> None:
        """Update only preferred_notification_channel for the user's existing row."""
        now = datetime.now(UTC)
        stmt = (
            user_preferences_table.update()
            .where(user_preferences_table.c.user_id == user_id)
            .values(
                preferred_notification_channel=channel,
                updated_at=now,
            )
        )

        with self._engine.begin() as conn:
            conn.execute(stmt)

    @staticmethod
    def _row_to_user_preferences(row: object) -> UserPreferences:
        return UserPreferences(
            user_id=row.user_id,  # type: ignore[attr-defined]
            default_ticket_duration_minutes=row.default_ticket_duration_minutes,  # type: ignore[attr-defined]
            auto_create_ticket=row.auto_create_ticket,  # type: ignore[attr-defined]
            preferred_notification_channel=row.preferred_notification_channel,  # type: ignore[attr-defined]
            notification_language=row.notification_language,  # type: ignore[attr-defined]
            updated_at=row.updated_at,  # type: ignore[attr-defined]
        )
