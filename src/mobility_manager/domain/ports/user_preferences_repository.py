"""
Port (interface): UserPreferencesRepository.

Abstract contract for per-user preferences persistence.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from mobility_manager.domain.entities.user_preferences import UserPreferences


class UserPreferencesRepository(ABC):
    """Abstract repository for user preferences entities."""

    @abstractmethod
    def update_with_notification_cascade(
        self,
        user_id: UUID,
        default_ticket_duration_minutes: int,
        auto_create_ticket: bool,
        preferred_notification_channel: str | None,
        notification_language: str | None,
        timezone: str | None,
        notification_cascade: list[tuple[str, bool]],
    ) -> UserPreferences:
        """
        Replace all five preference fields for the user's existing row and,
        in the same transaction, upsert `enabled` for each
        `(type_key, enabled)` pair in `notification_cascade` on that user's
        notification-preference rows — preserving each row's existing
        `config` and provisioning the row first if it doesn't already
        exist (ensure_defaults semantics), matching what
        NotificationPreferencesRepository.update does for a single row, but
        atomically alongside the preferences row itself.

        A mid-operation failure must roll back every write in this call,
        not just some — see PUT /preferences' auto_create_ticket cascade
        (post-implementation fix 11.6), which replaced `update()` followed
        by separate per-row writes specifically to close this atomicity
        gap. `notification_cascade` is empty when the caller has no cascade
        to apply (e.g. `auto_create_ticket` unchanged).
        """
        ...

    @abstractmethod
    def ensure_default(self, user_id: UUID) -> None:
        """
        Insert a default preferences row for user_id if one does not already exist.

        Must not modify an existing row (INSERT ... ON CONFLICT DO NOTHING semantics).
        """
        ...

    @abstractmethod
    def find_by_user_id(self, user_id: UUID) -> UserPreferences | None:
        """Return the preferences for the given user, or None if none exist."""
        ...

    @abstractmethod
    def update(
        self,
        user_id: UUID,
        default_ticket_duration_minutes: int,
        auto_create_ticket: bool,
        preferred_notification_channel: str | None,
        notification_language: str | None,
        timezone: str | None,
    ) -> UserPreferences:
        """Replace all five fields for the user's existing row and return the persisted UserPreferences."""
        ...

    @abstractmethod
    def set_preferred_notification_channel(self, user_id: UUID, channel: str | None) -> None:
        """
        Update only preferred_notification_channel for the user's existing row.

        Narrower than `update` — used by channel connect/disconnect flows
        (auto-select on first connect, clear on disconnect) so they don't
        need to round-trip the other preference fields they have no opinion
        about.
        """
        ...
