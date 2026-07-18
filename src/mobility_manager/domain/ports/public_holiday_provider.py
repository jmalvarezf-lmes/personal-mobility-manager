"""
Port (interface): PublicHolidayProvider.

Abstract contract for fetching the raw national public holiday calendar
feed. Mirrors the existing provider pattern (CityParkingDataProvider /
AmbientLabelLookupPort) — see add-ser-enforcement-calendar design.md D7/D11.

Fetching is deliberately kept separate from parsing: the same raw `.ics`
feed mixes real public holidays with non-holiday "celebrations", and
classifying an event as a holiday is per-city (see
`ical_holiday_parser.parse_ical_holidays`). So the provider fetches the raw
text exactly once per refresh run, and parsing/filtering happens once per
enabled city against that same raw text.
"""

from abc import ABC, abstractmethod


class PublicHolidayProvider(ABC):
    """Abstract provider for the raw national public holiday calendar feed."""

    @abstractmethod
    def fetch_raw_calendar(self) -> str:
        """
        Fetch the raw `.ics` calendar text, unparsed.

        Raises an exception on unrecoverable fetch errors — callers
        (e.g. RefreshPublicHolidays) are responsible for catching it and
        logging without crashing the scheduler (see design.md D7/D8).
        """
        ...
