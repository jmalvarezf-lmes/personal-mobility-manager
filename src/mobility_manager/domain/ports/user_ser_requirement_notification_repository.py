"""
Port (interface): UserSerRequirementNotificationRepository.

Abstract contract for persisting audit records of which user was notified
about a SER ticket requirement activation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class UserSerRequirementNotification:
    """Audit record for a notification sent about a requirement activation."""

    id: UUID
    user_id: UUID
    vehicle_id: UUID
    city_code: str | None
    zone_number: str | None
    latitude: float
    longitude: float
    requirement_activated_at: datetime
    notified_at: datetime


class UserSerRequirementNotificationRepository(ABC):
    """Abstract repository for SER requirement notification audit records."""

    @abstractmethod
    def save(self, notification: UserSerRequirementNotification) -> None:
        """Persist a notification audit record."""
        ...
