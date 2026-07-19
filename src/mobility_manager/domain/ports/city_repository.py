"""
Port (interface): CityRepository.

Abstract contract for reading the `cities` table — the single live source
of truth for which city codes are registered (see city-registry spec.md and
design.md D6/D7 of add-vehicle-ser-parking-exemption).
"""

from abc import ABC, abstractmethod

from mobility_manager.domain.entities.city import City


class CityRepository(ABC):
    """Abstract repository for the cities catalog."""

    @abstractmethod
    def list_all(self) -> list[City]:
        """Return every row currently in the `cities` table."""
        ...
