"""
Use case: RefreshPublicHolidays.

Fetches Spain's raw national holiday calendar once via the injected
PublicHolidayProvider, then parses+filters that same raw text once per
enabled city — the filtering is inherently per-city (design.md D11: the
same raw feed can yield different holiday sets for different cities) — and
upserts each city's resulting records into its `holidays` rows
(`source='ical_national'`) — see add-ser-enforcement-calendar design.md
D7/D11.

The fetch is shared across all cities (one HTTP call, one feed), so if it
fails the whole run is aborted before touching any city's data: logging
and returning without raising, matching MadridSerStreetsProvider's "log
which source failed, don't crash" convention. Per-city parsing can also
fail (a malformed feed raises `ValueError` from `Calendar.from_ical()`
inside `parse_ical_holidays`); the first such failure aborts the whole run
the same way, since a malformed raw calendar is a single upstream problem
shared by every city, not a per-city concern to isolate.
"""

import logging

import httpx

from mobility_manager.domain.ports.holiday_repository import HolidayRepository
from mobility_manager.domain.ports.public_holiday_provider import PublicHolidayProvider
from mobility_manager.infrastructure.holiday_calendar.ical_holiday_parser import (
    parse_ical_holidays,
)

logger = logging.getLogger(__name__)


class RefreshPublicHolidays:
    """Use case that refreshes national public holidays for a fixed set of cities."""

    def __init__(
        self,
        provider: PublicHolidayProvider,
        holiday_repo: HolidayRepository,
        city_codes: list[str],
    ) -> None:
        self._provider = provider
        self._holiday_repo = holiday_repo
        self._city_codes = city_codes

    def execute(self) -> None:
        """
        Fetch once, then parse+filter and upsert into every configured city's holidays.

        Never raises: a provider fetch failure, or a parse/filter failure
        for any city, is logged and the run returns without modifying any
        city's data further.
        """
        try:
            raw_calendar = self._provider.fetch_raw_calendar()
        except (RuntimeError, httpx.HTTPError):
            # RuntimeError/httpx.HTTPError cover fetch failures (non-2xx
            # response, network error).
            logger.exception("Public holiday calendar fetch failed — leaving existing holidays untouched")
            return

        total_upserted = 0
        try:
            for city_code in self._city_codes:
                city_holidays = parse_ical_holidays(raw_calendar, city_code)
                self._holiday_repo.upsert_national_holidays(city_code, city_holidays)
                total_upserted += len(city_holidays)
        except ValueError:
            # icalendar.Calendar.from_ical() raises ValueError on malformed/
            # non-RFC-5545 .ics input (see ical_holiday_parser.py). A
            # malformed raw calendar is a single upstream problem shared by
            # every city, so the first failure aborts the remaining cities.
            logger.exception("Public holiday calendar fetch or parse failed — leaving existing holidays untouched")
            return

        logger.info(
            "Public holiday refresh complete: %d holiday(s) upserted across %d cit(y/ies)",
            total_upserted,
            len(self._city_codes),
        )
