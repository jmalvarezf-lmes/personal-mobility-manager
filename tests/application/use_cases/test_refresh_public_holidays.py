"""
Unit tests for RefreshPublicHolidays.

Uses fake PublicHolidayProvider/HolidayRepository implementations (no live
DB/HTTP), following the fake-port convention used elsewhere in
tests/application/use_cases/. Covers the `public-holiday-calendar` spec's
"Refresh inserts one row per enabled city per applicable holiday", "Two
cities can receive different holiday sets from the same fetch", and
"Refresh never touches manual rows" scenarios, plus the idempotent-upsert
requirement from add-ser-enforcement-calendar tasks.md 8.7/10.4.
"""

import logging
from datetime import date

import httpx
import pytest

from mobility_manager.application.use_cases.refresh_public_holidays import (
    RefreshPublicHolidays,
)
from mobility_manager.domain.value_objects.holiday_record import HolidayRecord

_RAW_CALENDAR_TWO_NATIONAL_HOLIDAYS = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:1@test
DTSTART;VALUE=DATE:20260101
DTEND;VALUE=DATE:20260102
SUMMARY:Ano Nuevo
DESCRIPTION:Día festivo
END:VEVENT
BEGIN:VEVENT
UID:2@test
DTSTART;VALUE=DATE:20260106
DTEND;VALUE=DATE:20260107
SUMMARY:Epifania del Senor
DESCRIPTION:Día festivo
END:VEVENT
END:VCALENDAR
"""

# One national holiday (kept for every city) plus one regional event naming
# only "madrid" — used to prove two cities can get different holiday sets
# from one shared fetch (public-holiday-calendar spec: "Two cities can
# receive different holiday sets from the same fetch").
_RAW_CALENDAR_ONE_NATIONAL_ONE_REGIONAL_MADRID_ONLY = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:1@test
DTSTART;VALUE=DATE:20260101
DTEND;VALUE=DATE:20260102
SUMMARY:Ano Nuevo
DESCRIPTION:Día festivo
END:VEVENT
BEGIN:VEVENT
UID:2@test
DTSTART;VALUE=DATE:20260502
DTEND;VALUE=DATE:20260503
SUMMARY:Fiesta del Trabajo (festivo regional)
DESCRIPTION:Celebración en Madrid\\nPara ocultar las celebraciones\\, ve a Configuración en Google Calendar > Festivos en España
END:VEVENT
END:VCALENDAR
"""

_MALFORMED_RAW_CALENDAR = "this is not a valid ics payload at all"


class _FakeHolidayRepo:
    """
    Fake HolidayRepository tracking upsert calls and simulating upsert
    (ON CONFLICT DO UPDATE) semantics for `source='ical_national'` rows,
    while keeping a separate, never-written-to store for `source='manual'`
    rows — mirroring the real schema's separation by `source`.
    """

    def __init__(self) -> None:
        self.manual_rows: dict[tuple[str, date], str] = {}
        self.ical_national_rows: dict[tuple[str, date], str] = {}
        self.upsert_calls: list[tuple[str, list[HolidayRecord]]] = []

    def upsert_national_holidays(self, city_code: str, holidays: list[HolidayRecord]) -> None:
        self.upsert_calls.append((city_code, holidays))
        for h in holidays:
            self.ical_national_rows[(city_code, h.date)] = h.name

    def has_no_national_holidays(self, city_code: str) -> bool:
        return not any(key[0] == city_code for key in self.ical_national_rows)


class _FakeProvider:
    def __init__(self, raw_calendar: str = "", raise_error: Exception | None = None) -> None:
        self._raw_calendar = raw_calendar
        self._raise_error = raise_error

    def fetch_raw_calendar(self) -> str:
        if self._raise_error is not None:
            raise self._raise_error
        return self._raw_calendar


def test_refresh_inserts_one_row_per_enabled_city_per_holiday() -> None:
    repo = _FakeHolidayRepo()
    use_case = RefreshPublicHolidays(
        provider=_FakeProvider(raw_calendar=_RAW_CALENDAR_TWO_NATIONAL_HOLIDAYS),
        holiday_repo=repo,
        city_codes=["madrid"],
    )

    use_case.execute()

    assert len(repo.ical_national_rows) == 2
    assert repo.ical_national_rows[("madrid", date(2026, 1, 1))] == "Ano Nuevo"
    assert repo.ical_national_rows[("madrid", date(2026, 1, 6))] == "Epifania del Senor"


def test_refresh_inserts_rows_for_every_configured_city() -> None:
    repo = _FakeHolidayRepo()
    use_case = RefreshPublicHolidays(
        provider=_FakeProvider(raw_calendar=_RAW_CALENDAR_TWO_NATIONAL_HOLIDAYS),
        holiday_repo=repo,
        city_codes=["madrid", "barcelona"],
    )

    use_case.execute()

    assert len(repo.ical_national_rows) == 4
    assert ("madrid", date(2026, 1, 1)) in repo.ical_national_rows
    assert ("barcelona", date(2026, 1, 1)) in repo.ical_national_rows


def test_refresh_gives_different_cities_different_holiday_sets_from_one_fetch() -> None:
    """
    One shared fetch, one national holiday (kept for both cities) and one
    regional event naming only "madrid" — madrid should get both dates,
    barcelona only the national one.
    """
    repo = _FakeHolidayRepo()
    use_case = RefreshPublicHolidays(
        provider=_FakeProvider(raw_calendar=_RAW_CALENDAR_ONE_NATIONAL_ONE_REGIONAL_MADRID_ONLY),
        holiday_repo=repo,
        city_codes=["madrid", "barcelona"],
    )

    use_case.execute()

    assert ("madrid", date(2026, 1, 1)) in repo.ical_national_rows
    assert ("madrid", date(2026, 5, 2)) in repo.ical_national_rows
    assert ("barcelona", date(2026, 1, 1)) in repo.ical_national_rows
    assert ("barcelona", date(2026, 5, 2)) not in repo.ical_national_rows

    madrid_calls = [holidays for city_code, holidays in repo.upsert_calls if city_code == "madrid"]
    barcelona_calls = [holidays for city_code, holidays in repo.upsert_calls if city_code == "barcelona"]
    assert len(madrid_calls[0]) == 2
    assert len(barcelona_calls[0]) == 1


def test_refresh_upsert_is_idempotent_calling_twice_does_not_duplicate() -> None:
    repo = _FakeHolidayRepo()
    use_case = RefreshPublicHolidays(
        provider=_FakeProvider(raw_calendar=_RAW_CALENDAR_TWO_NATIONAL_HOLIDAYS),
        holiday_repo=repo,
        city_codes=["madrid"],
    )

    use_case.execute()
    use_case.execute()

    assert len(repo.upsert_calls) == 2  # the use case does call upsert each run...
    assert len(repo.ical_national_rows) == 2  # ...but the stored data is not duplicated


def test_refresh_never_touches_manual_rows() -> None:
    repo = _FakeHolidayRepo()
    repo.manual_rows[("madrid", date(2026, 5, 2))] = "Fiesta de la Comunidad de Madrid"
    manual_rows_before = dict(repo.manual_rows)

    use_case = RefreshPublicHolidays(
        provider=_FakeProvider(raw_calendar=_RAW_CALENDAR_TWO_NATIONAL_HOLIDAYS),
        holiday_repo=repo,
        city_codes=["madrid"],
    )

    use_case.execute()

    assert repo.manual_rows == manual_rows_before


def test_refresh_never_raises_when_provider_raises_runtime_error() -> None:
    repo = _FakeHolidayRepo()
    use_case = RefreshPublicHolidays(
        provider=_FakeProvider(raise_error=RuntimeError("fetch failed: HTTP 503")),
        holiday_repo=repo,
        city_codes=["madrid"],
    )

    use_case.execute()  # must not raise

    assert repo.upsert_calls == []
    assert repo.ical_national_rows == {}


def test_refresh_never_raises_when_provider_raises_httpx_error() -> None:
    repo = _FakeHolidayRepo()
    use_case = RefreshPublicHolidays(
        provider=_FakeProvider(raise_error=httpx.ConnectTimeout("timed out")),
        holiday_repo=repo,
        city_codes=["madrid"],
    )

    use_case.execute()  # must not raise

    assert repo.upsert_calls == []


def test_refresh_never_raises_when_calendar_is_malformed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    icalendar.Calendar.from_ical() raises ValueError on malformed/non-RFC-5545
    .ics input (see ical_holiday_parser.py's parse_ical_holidays(), called
    once per city from execute()) — execute()'s own except clause must catch
    this parse failure directly, not merely rely on HolidayRefreshScheduler's
    separate outer except Exception.
    """
    repo = _FakeHolidayRepo()
    use_case = RefreshPublicHolidays(
        provider=_FakeProvider(raw_calendar=_MALFORMED_RAW_CALENDAR),
        holiday_repo=repo,
        city_codes=["madrid"],
    )

    with caplog.at_level(logging.ERROR):
        use_case.execute()  # must not raise

    assert repo.upsert_calls == []
    assert any("fetch or parse failed" in record.message for record in caplog.records)
