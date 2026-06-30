"""
Port (interface): UserRepository.

Abstract contract for user entity persistence.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from mobility_manager.domain.entities.user import User


class UserRepository(ABC):
    """Abstract repository for user entities."""

    @abstractmethod
    def upsert(self, google_sub: str, email: str, display_name: str) -> User:
        """
        Insert or update a user identified by google_sub.

        If a user with the given google_sub already exists, update email and
        display_name. Returns the persisted User entity.
        """
        ...

    @abstractmethod
    def find_by_id(self, user_id: UUID) -> User | None:
        """Return the user with the given UUID, or None if not found."""
        ...
