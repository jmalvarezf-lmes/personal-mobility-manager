"""
Port (interface): CityParkingDataProvider.

Abstract contract for city-specific parking data ingestion. Each city
implements this to own its full fetch-and-parse pipeline.
"""

from abc import ABC, abstractmethod

from mobility_manager.domain.value_objects.parking_spot_record import ParkingSpotRecord


class CityParkingDataProvider(ABC):
    """Abstract provider for city parking spot data."""

    @property
    @abstractmethod
    def city_code(self) -> str:
        """Short identifier for the city (e.g. 'madrid')."""
        ...

    @abstractmethod
    def get_records(self) -> list[ParkingSpotRecord]:
        """
        Fetch and parse parking spot records for this city.

        Raises an exception on unrecoverable fetch errors. Rows that fail
        parsing or have unrecognised zone types are skipped internally.
        """
        ...
