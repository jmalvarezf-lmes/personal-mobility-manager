"""
Unit tests for parse_ical_holidays().

Covers the `PublicHolidayProvider port and Google Calendar iCal
implementation` requirement's "Successful fetch and parse" scenario, the
defensive DATE/DATETIME/missing-field handling described in the module's
own docstring, and every scenario in the `Filter calendar events to
genuine, city-applicable public holidays only` requirement — see
add-ser-enforcement-calendar tasks.md 8.6/10.4 and design.md D11.
"""

from datetime import date

from mobility_manager.infrastructure.holiday_calendar.ical_holiday_parser import (
    parse_ical_holidays,
)

_VALID_ICS_ALL_DAY_EVENTS = """\
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

_ICS_WITH_DATETIME_EVENT = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:1@test
DTSTART:20260106T000000Z
DTEND:20260107T000000Z
SUMMARY:Epifania del Senor
DESCRIPTION:Día festivo
END:VEVENT
END:VCALENDAR
"""

_ICS_MISSING_SUMMARY = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:1@test
DTSTART;VALUE=DATE:20260101
DTEND;VALUE=DATE:20260102
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

_ICS_NO_EVENTS = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Test//Test//EN\nEND:VCALENDAR\n"


def test_parses_all_day_date_events() -> None:
    records = parse_ical_holidays(_VALID_ICS_ALL_DAY_EVENTS, "madrid")

    assert len(records) == 2
    assert records[0].date == date(2026, 1, 1)
    assert records[0].name == "Ano Nuevo"
    assert records[1].date == date(2026, 1, 6)
    assert records[1].name == "Epifania del Senor"


def test_parses_datetime_events_defensively() -> None:
    """Google's feed uses all-day DATE events, but DATETIME must still parse (see module docstring)."""
    records = parse_ical_holidays(_ICS_WITH_DATETIME_EVENT, "madrid")

    assert len(records) == 1
    assert records[0].date == date(2026, 1, 6)
    assert records[0].name == "Epifania del Senor"


def test_skips_event_missing_summary_and_keeps_others() -> None:
    records = parse_ical_holidays(_ICS_MISSING_SUMMARY, "madrid")

    assert len(records) == 1
    assert records[0].name == "Epifania del Senor"


def test_returns_empty_list_for_calendar_with_no_events() -> None:
    assert parse_ical_holidays(_ICS_NO_EVENTS, "madrid") == []


# ---------------------------------------------------------------------------
# Filtering to genuine, city-applicable public holidays (design.md D11)
# ---------------------------------------------------------------------------


def _ics_with_description(description: str) -> str:
    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Test//Test//EN\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:1@test\r\n"
        "DTSTART;VALUE=DATE:20260101\r\n"
        "DTEND;VALUE=DATE:20260102\r\n"
        "SUMMARY:Test Event\r\n"
        f"DESCRIPTION:{description}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )


def test_national_holiday_is_kept_for_any_city() -> None:
    ics = _ics_with_description("Día festivo")

    assert len(parse_ical_holidays(ics, "madrid")) == 1
    assert len(parse_ical_holidays(ics, "barcelona")) == 1


def test_generic_celebration_with_no_region_list_is_excluded() -> None:
    ics = _ics_with_description(
        "Celebración\\nPara ocultar las celebraciones\\, ve a Configuración en "
        "Google Calendar > Festivos en España"
    )

    assert parse_ical_holidays(ics, "madrid") == []
    assert parse_ical_holidays(ics, "barcelona") == []


def test_regional_entry_naming_target_city_is_kept_for_that_city() -> None:
    ics = _ics_with_description(
        "Celebración en Andalucía\\, Aragón\\, Madrid\\, Murcia"
        "\\nPara ocultar las celebraciones\\, ve a Configuración en Google Calendar > Festivos en España"
    )

    records = parse_ical_holidays(ics, "madrid")

    assert len(records) == 1
    assert records[0].date == date(2026, 1, 1)


def test_regional_entry_not_naming_target_city_is_excluded_for_that_city() -> None:
    ics = _ics_with_description(
        "Celebración en Andalucía\\, Aragón\\, Madrid\\, Murcia"
        "\\nPara ocultar las celebraciones\\, ve a Configuración en Google Calendar > Festivos en España"
    )

    assert parse_ical_holidays(ics, "barcelona") == []


def test_region_list_matching_is_exact_entry_not_substring() -> None:
    """
    A naive `city_code.capitalize() in description` substring check would
    false-positive here: "Madrid" is a substring of the synthetic region
    entry "Madridejos", but "Madridejos" is not an exact match for "Madrid".
    Exact-entry matching must exclude this event for "madrid".
    """
    ics = _ics_with_description(
        "Celebración en Andalucía\\, Madridejos\\, Murcia"
        "\\nPara ocultar las celebraciones\\, ve a Configuración en Google Calendar > Festivos en España"
    )

    assert parse_ical_holidays(ics, "madrid") == []
    # "Madridejos" IS an exact entry in the list, so it correctly matches
    # for that (synthetic) city — confirming the matching is exact-entry
    # rather than a blanket "never match a name containing madrid" rule.
    assert len(parse_ical_holidays(ics, "madridejos")) == 1
