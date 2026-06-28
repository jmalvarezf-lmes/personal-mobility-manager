"""
Port (interface): SerZoneRepository.

Abstract contract for SER zone data persistence.
"""

from abc import ABC, abstractmethod

from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.value_objects.location import GeoLocation


class SerZoneRepository(ABC):
    """Abstract repository for SER zone data."""

    @abstractmethod
    def find_nearest(
        self,
        location: GeoLocation,
        radius_deg: float = 0.01,
    ) -> SerZone | None:
        """Find the nearest SER zone within radius_deg degrees of the given location."""
        ...

    @abstractmethod
    def list_all(self) -> list[SerZone]:
        """Return all stored SER zones."""
        ...
