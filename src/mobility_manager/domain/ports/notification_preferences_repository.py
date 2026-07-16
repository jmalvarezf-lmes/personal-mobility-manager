"""
Port (interface): NotificationPreferencesRepository.

Abstract contract for the notification_types catalog and per-user, per-type
notification preferences persistence. Kept separate from
UserPreferencesRepository — see design.md decision 8 — because the shape
(catalog-joined, one row per (user, type)) and its consumers (event
handlers, the notification-preferences API) are distinct from
UserPreferencesRepository's single scalar-field row per user.
"""

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from mobility_manager.domain.entities.notification_type import NotificationType
from mobility_manager.domain.entities.user_notification_preference import (
    UserNotificationPreference,
)


class NotificationPreferencesRepository(ABC):
    """Abstract repository for the notification types catalog and user preferences."""

    @abstractmethod
    def list_types(self) -> list[NotificationType]:
        """Return every row in the notification_types catalog."""
        ...

    @abstractmethod
    def ensure_defaults(self, user_id: UUID) -> None:
        """
        Insert a disabled default preference row (enabled=false, config={})
        for user_id, for every notification_types row without a matching
        (user_id, type_key) row.

        Must not modify an existing row (INSERT ... ON CONFLICT DO NOTHING
        semantics) — this is an opt-in model, a user is never auto-enrolled
        into a notification type.
        """
        ...

    @abstractmethod
    def find_by_user_id(self, user_id: UUID) -> list[UserNotificationPreference]:
        """Return the user's preference rows, one per type they have a row for."""
        ...

    @abstractmethod
    def find_by_user_id_and_type(self, user_id: UUID, type_key: str) -> UserNotificationPreference | None:
        """
        Return the user's single (user_id, type_key) preference row, or None
        if no such row exists.

        A direct, single-row lookup rather than fetching every row via
        find_by_user_id and scanning in Python — used by the event handlers,
        which only ever need one type's preference per event.
        """
        ...

    @abstractmethod
    def update(
        self,
        user_id: UUID,
        type_key: str,
        enabled: bool,
        config: dict[str, Any],
    ) -> UserNotificationPreference:
        """
        Replace `enabled` and `config` for the user's (user_id, type_key) row
        and return the persisted value.

        Inserts the row first (ensure_defaults semantics) if it doesn't
        already exist, so a caller never has to sequence ensure_defaults
        before update itself.
        """
        ...
