"""
Port (interface): UserNotificationChannelConfigRepository.

Abstract contract for per-user, per-channel notification recipient storage.
Scoped to user_id (not vehicle_id) since notification channels are personal,
mirroring UserSerProviderConfigRepository's shape — but unlike that
repository, implementations of this port MUST NOT encrypt the stored
payload (see design.md decision 3): a channel identifier like a Telegram
chat_id is not a credential.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from mobility_manager.domain.value_objects.notification_recipient import (
    NotificationRecipient,
)


class UserNotificationChannelConfigRepository(ABC):
    """Abstract repository for per-user notification channel configuration."""

    @abstractmethod
    def save(self, user_id: UUID, channel: str, recipient: NotificationRecipient) -> None:
        """Persist (upsert) the recipient for the given (user_id, channel) pair."""
        ...

    @abstractmethod
    def find(self, user_id: UUID, channel: str) -> NotificationRecipient | None:
        """Return the stored recipient for (user_id, channel), or None if none exists."""
        ...

    @abstractmethod
    def find_all_by_user_id(self, user_id: UUID) -> list[tuple[str, NotificationRecipient]]:
        """Return all (channel, recipient) pairs configured for `user_id`."""
        ...

    @abstractmethod
    def delete(self, user_id: UUID, channel: str) -> None:
        """Remove the stored recipient for (user_id, channel), if present. Idempotent — never raises if absent."""
        ...
