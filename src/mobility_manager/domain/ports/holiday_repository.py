"""
Port (interface): HolidayRepository.

Abstract contract for persisting per-city public holidays, for hexagonal
consistency with `SerZoneRepository`/`VehicleAmbientLabelRepository` —
application-layer use cases (e.g. `RefreshPublicHolidays`) depend on this
abstraction rather than on the concrete `PostgresHolidayRepository` class
(see design.md D3/D7).
"""

from abc import ABC, abstractmethod

from mobility_manager.domain.value_objects.holiday_record import HolidayRecord


class HolidayRepository(ABC):
    """Abstract repository for per-city public holidays."""

    @abstractmethod
    def upsert_national_holidays(self, city_code: str, holidays: list[HolidayRecord]) -> None:
        """
        Insert or update `source='ical_national'` rows for `city_code`.

        Never touches `source='manual'` rows and never issues a blanket
        delete (see design.md D3).
        """
        ...

    @abstractmethod
    def has_no_national_holidays(self, city_code: str) -> bool:
        """Return True if `city_code` has zero `source='ical_national'` rows in `holidays`."""
        ...
