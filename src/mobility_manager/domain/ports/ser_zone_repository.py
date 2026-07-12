"""
Port (interface): SerZoneRepository.

Abstract contract for SER zone data persistence.
"""

from abc import ABC, abstractmethod

from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.value_objects.location import GeoLocation
from mobility_manager.domain.value_objects.zone_area import ZoneArea


class SerZoneRepository(ABC):
    """Abstract repository for SER zone data."""

    @abstractmethod
    def find_nearest(self, location: GeoLocation) -> SerZone | None:
        """
        Find the SER zone nearest to the given location.

        Distance is measured to each zone's polygon geometry (zero if the
        point is inside the zone). No SQL bounding-box prefilter is used —
        see design.md D5.
        """
        ...

    @abstractmethod
    def find_containing(self, location: GeoLocation) -> SerZone | None:
        """Find the SER zone whose polygon contains the given location, or None."""
        ...

    @abstractmethod
    def list_all(self) -> list[SerZone]:
        """Return all stored SER zones."""
        ...

    @abstractmethod
    def get_street_names(self, zone_number: str, zone_type: str) -> list[str]:
        """
        Return all street names associated with the given (zone_number, zone_type).

        This is a targeted query against ser_zone_streets only — never joined
        into list_all()/find_nearest()/find_containing() (see design.md D9).
        """
        ...

    @abstractmethod
    def get_zone_area(self, zone_number: str) -> ZoneArea | None:
        """
        Return the frontier (neighbourhood name + geometry) for the given
        zone_number, or None if no ser_zone_areas row exists for it.

        This is a targeted query against ser_zone_areas only — never joined
        into list_all()/find_nearest()/find_containing() (see
        add-ser-zone-frontiers design.md D6).
        """
        ...

    @abstractmethod
    def list_zone_areas(self) -> list[ZoneArea]:
        """
        Return all stored frontiers (one ZoneArea per ser_zone_areas row).

        This is a targeted query against ser_zone_areas only — never joined
        into list_all()/find_nearest()/find_containing().
        """
        ...
