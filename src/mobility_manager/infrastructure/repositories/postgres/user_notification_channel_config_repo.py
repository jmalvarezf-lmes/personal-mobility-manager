"""
Infrastructure: PostgresUserNotificationChannelConfigRepository.

Stores per-user, per-channel notification recipients: JSON-serialised
payload in cleartext — deliberately NOT Fernet-encrypted, unlike
PostgresUserSerProviderConfigRepository's treatment of SER provider
sessions. A Telegram chat_id (or any future channel's recipient data) is an
identifier, not a credential — see design.md decision 3.
"""

import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from mobility_manager.domain.ports.user_notification_channel_config_repository import (
    UserNotificationChannelConfigRepository,
)
from mobility_manager.domain.value_objects.notification_recipient import (
    NotificationRecipient,
)
from mobility_manager.infrastructure.orm.tables import (
    user_notification_channel_configs_table,
)


class PostgresUserNotificationChannelConfigRepository(UserNotificationChannelConfigRepository):
    """PostgreSQL-backed per-user notification channel configuration repository."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def save(self, user_id: UUID, channel: str, recipient: NotificationRecipient) -> None:
        """Serialise recipient.data to plain JSON (no encryption) and upsert the row for (user_id, channel)."""
        config_json = json.dumps(recipient.data)
        now = datetime.now(UTC)

        stmt = pg_insert(user_notification_channel_configs_table).values(
            user_id=user_id,
            channel=channel,
            config=config_json,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "channel"],
            set_={"config": config_json, "updated_at": now},
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def find(self, user_id: UUID, channel: str) -> NotificationRecipient | None:
        """Return the deserialised recipient for (user_id, channel), or None if absent."""
        with self._engine.connect() as conn:
            row = conn.execute(
                select(user_notification_channel_configs_table.c.config).where(
                    user_notification_channel_configs_table.c.user_id == user_id,
                    user_notification_channel_configs_table.c.channel == channel,
                )
            ).fetchone()

        if row is None:
            return None

        return NotificationRecipient(data=json.loads(row.config))

    def find_all_by_user_id(self, user_id: UUID) -> list[tuple[str, NotificationRecipient]]:
        """Return all (channel, recipient) pairs configured for `user_id`."""
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(
                    user_notification_channel_configs_table.c.channel,
                    user_notification_channel_configs_table.c.config,
                ).where(
                    user_notification_channel_configs_table.c.user_id == user_id,
                )
            ).fetchall()

        return [(row.channel, NotificationRecipient(data=json.loads(row.config))) for row in rows]

    def delete(self, user_id: UUID, channel: str) -> None:
        """Remove the stored recipient for (user_id, channel), if present. Idempotent — never raises if absent."""
        stmt = sa_delete(user_notification_channel_configs_table).where(
            user_notification_channel_configs_table.c.user_id == user_id,
            user_notification_channel_configs_table.c.channel == channel,
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)
