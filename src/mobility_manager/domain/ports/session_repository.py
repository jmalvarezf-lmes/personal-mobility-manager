"""
Port (interface): SessionRepository.

Abstract contract for server-side session persistence — see
add-session-revocation design.md.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from mobility_manager.domain.entities.session import Session


class SessionRepository(ABC):
    """Abstract repository for session entities."""

    @abstractmethod
    def create(self, user_id: UUID, expires_at: datetime) -> Session:
        """Create and persist a new session for user_id, expiring at expires_at."""
        ...

    @abstractmethod
    def find_by_id(self, session_id: UUID) -> Session | None:
        """Return the session with the given UUID, or None if not found."""
        ...

    @abstractmethod
    def revoke(self, session_id: UUID) -> None:
        """
        Set revoked_at to now() on the session with the given UUID.

        No-ops silently if the session doesn't exist (idempotent).
        """
        ...

    @abstractmethod
    def delete_older_than(self, cutoff: datetime) -> int:
        """
        Delete sessions whose revoked_at or expires_at predate cutoff.

        Returns the number of rows deleted.
        """
        ...
