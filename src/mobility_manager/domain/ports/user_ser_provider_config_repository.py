"""
Port (interface): UserSerProviderConfigRepository.

Abstract contract for per-user, per-provider SER session storage. Scoped to
user_id (not vehicle_id) because SER provider accounts are personal, not
per-vehicle — a departure from VehicleConfigRepository's per-vehicle shape.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from mobility_manager.domain.value_objects.ser_provider_session import (
    SerProviderSession,
)


class UserSerProviderConfigRepository(ABC):
    """Abstract repository for per-user SER provider sessions."""

    @abstractmethod
    def save(self, user_id: UUID, provider: str, session: SerProviderSession) -> None:
        """Persist (upsert) the session for the given (user_id, provider) pair."""
        ...

    @abstractmethod
    def find(self, user_id: UUID, provider: str) -> SerProviderSession | None:
        """Return the stored session for (user_id, provider), or None if none exists."""
        ...
