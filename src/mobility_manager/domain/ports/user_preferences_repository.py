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
    ) -> UserPreferences:
        """Replace both fields for the user's existing row and return the persisted UserPreferences."""
        ...
