"""
Port (interface): CityParkingDataProvider.

Abstract contract for city-specific parking data ingestion. Each city
implements this to own its full fetch-and-parse pipeline.
"""

from abc import ABC, abstractmethod

from mobility_manager.domain.value_objects.ser_zone_boundary_record import (
    SerZoneBoundaryRecord,
)
from mobility_manager.domain.value_objects.zone_area import ZoneArea


class CityParkingDataProvider(ABC):
    """Abstract provider for city parking spot data."""

    @property
    @abstractmethod
    def city_code(self) -> str:
        """Short identifier for the city (e.g. 'madrid')."""
        ...

    @abstractmethod
    def get_records(self) -> list[SerZoneBoundaryRecord]:
        """
        Fetch and parse parking spot records for this city.

        Raises an exception on unrecoverable fetch errors. Rows that fail
        parsing or have unrecognised zone types are skipped internally.
        """
        ...

    @abstractmethod
    def get_zone_areas(self) -> list[ZoneArea]:
        """
        Fetch and resolve one presentation-only frontier (ZoneArea) per
        resolvable zone_number for this city.

        Raises an exception on unrecoverable fetch errors. A zone_number
        whose frontier cannot be resolved is skipped internally (absent from
        the result), not given a fallback/synthesized geometry.
        """
        ...

    @abstractmethod
    def get_records_and_zone_areas(self) -> tuple[list[SerZoneBoundaryRecord], list[ZoneArea]]:
        """
        Fetch records and zone areas together, sharing one fetch/parse of any
        upstream sources both need.

        Equivalent to calling get_records() followed by get_zone_areas(), but
        without re-fetching/re-parsing shared sources twice within the same
        call — use this instead of calling both separately when both results
        are needed for the same ingestion run.
        """
        ...
