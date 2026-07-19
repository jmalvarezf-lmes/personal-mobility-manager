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
    def list_zones_for_city(self, city_code: str) -> list[SerZone]:
        """
        Return only the SER zones stored for `city_code`.

        Unlike list_all(), this is scoped with a WHERE city_code clause —
        used by GET /parking/ser-zones, which must never leak another
        city's zones into a single-city response (see
        add-vehicle-ser-parking-exemption design.md D7). list_all() stays
        unscoped for find_containing()/find_nearest(), which don't know the
        city in advance.
        """
        ...

    @abstractmethod
    def get_street_names(self, city_code: str, zone_number: str, zone_type: str) -> list[str]:
        """
        Return all street names associated with the given
        (city_code, zone_number, zone_type).

        This is a targeted query against ser_zone_streets only — never joined
        into list_all()/find_nearest()/find_containing() (see design.md D9).
        city_code disambiguates zone_number/zone_type pairs that may collide
        across cities (see add-ser-enforcement-calendar design.md D5).
        """
        ...

    @abstractmethod
    def get_zone_area(self, city_code: str, zone_number: str) -> ZoneArea | None:
        """
        Return the frontier (neighbourhood name + geometry) for the given
        (city_code, zone_number), or None if no ser_zone_areas row exists for
        it.

        This is a targeted query against ser_zone_areas only — never joined
        into list_all()/find_nearest()/find_containing() (see
        add-ser-zone-frontiers design.md D6). city_code disambiguates
        zone_number values that may collide across cities (see
        add-ser-enforcement-calendar design.md D5).
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

    @abstractmethod
    def list_zone_areas_for_city(self, city_code: str) -> list[ZoneArea]:
        """
        Return only the frontiers stored for `city_code`.

        Unlike list_zone_areas(), this is scoped with a WHERE city_code
        clause — used by GET /parking/ser-zones (see design.md D7 of
        add-vehicle-ser-parking-exemption).
        """
        ...
