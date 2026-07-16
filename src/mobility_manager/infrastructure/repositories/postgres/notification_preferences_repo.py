"""
Infrastructure: PostgresNotificationPreferencesRepository.

SQLAlchemy Core implementation of the NotificationPreferencesRepository
port. Uses INSERT ... SELECT ... ON CONFLICT DO NOTHING for ensure_defaults
(mirroring the migration backfill's shape) and INSERT ... ON CONFLICT DO
UPDATE for update (so a row is provisioned on first write without requiring
callers to sequence ensure_defaults first).
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from mobility_manager.domain.entities.notification_type import NotificationType
from mobility_manager.domain.entities.user_notification_preference import (
    UserNotificationPreference,
)
from mobility_manager.domain.ports.notification_preferences_repository import (
    NotificationPreferencesRepository,
)
from mobility_manager.infrastructure.orm.tables import (
    notification_types_table,
    user_notification_preferences_table,
)

_DEFAULT_ENABLED = False
_DEFAULT_CONFIG: dict[str, Any] = {}


class PostgresNotificationPreferencesRepository(NotificationPreferencesRepository):
    """PostgreSQL-backed notification preferences repository using SQLAlchemy Core."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def list_types(self) -> list[NotificationType]:
        """Return every row in the notification_types catalog."""
        with self._engine.connect() as conn:
            rows = conn.execute(select(notification_types_table).order_by(notification_types_table.c.key)).fetchall()
        return [self._row_to_notification_type(row) for row in rows]

    def ensure_defaults(self, user_id: UUID) -> None:
        """
        Insert a disabled (enabled=false, config={}) row for every
        notification_types row without a matching (user_id, type_key) row.

        Uses INSERT ... SELECT ... ON CONFLICT (user_id, type_key) DO
        NOTHING so any already-customized row is never touched.
        """
        now = datetime.now(UTC)
        with self._engine.begin() as conn:
            type_keys = [row.key for row in conn.execute(select(notification_types_table.c.key)).fetchall()]
            if not type_keys:
                return
            stmt = (
                insert(user_notification_preferences_table)
                .values(
                    [
                        {
                            "user_id": user_id,
                            "type_key": type_key,
                            "enabled": _DEFAULT_ENABLED,
                            "config": _DEFAULT_CONFIG,
                            "updated_at": now,
                        }
                        for type_key in type_keys
                    ]
                )
                .on_conflict_do_nothing(index_elements=["user_id", "type_key"])
            )
            conn.execute(stmt)

    def find_by_user_id(self, user_id: UUID) -> list[UserNotificationPreference]:
        """Return the user's preference rows, one per type they have a row for."""
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(user_notification_preferences_table)
                .where(user_notification_preferences_table.c.user_id == user_id)
                .order_by(user_notification_preferences_table.c.type_key)
            ).fetchall()
        return [self._row_to_user_notification_preference(row) for row in rows]

    def find_by_user_id_and_type(self, user_id: UUID, type_key: str) -> UserNotificationPreference | None:
        """Return the user's single (user_id, type_key) row, or None if absent."""
        with self._engine.connect() as conn:
            row = conn.execute(
                select(user_notification_preferences_table).where(
                    user_notification_preferences_table.c.user_id == user_id,
                    user_notification_preferences_table.c.type_key == type_key,
                )
            ).fetchone()
        return self._row_to_user_notification_preference(row) if row is not None else None

    def update(
        self,
        user_id: UUID,
        type_key: str,
        enabled: bool,
        config: dict[str, Any],
    ) -> UserNotificationPreference:
        """
        Replace `enabled` and `config` for the user's (user_id, type_key)
        row, inserting it first if absent, and return the persisted value.
        """
        now = datetime.now(UTC)
        stmt = (
            insert(user_notification_preferences_table)
            .values(
                user_id=user_id,
                type_key=type_key,
                enabled=enabled,
                config=config,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "type_key"],
                set_={"enabled": enabled, "config": config, "updated_at": now},
            )
            .returning(user_notification_preferences_table)
        )

        with self._engine.begin() as conn:
            row = conn.execute(stmt).fetchone()

        assert row is not None
        return self._row_to_user_notification_preference(row)

    @staticmethod
    def _row_to_notification_type(row: object) -> NotificationType:
        return NotificationType(
            key=row.key,  # type: ignore[attr-defined]
            label=row.label,  # type: ignore[attr-defined]
            config_schema=row.config_schema,  # type: ignore[attr-defined]
        )

    @staticmethod
    def _row_to_user_notification_preference(row: object) -> UserNotificationPreference:
        return UserNotificationPreference(
            user_id=row.user_id,  # type: ignore[attr-defined]
            type_key=row.type_key,  # type: ignore[attr-defined]
            enabled=row.enabled,  # type: ignore[attr-defined]
            config=row.config,  # type: ignore[attr-defined]
            updated_at=row.updated_at,  # type: ignore[attr-defined]
        )
