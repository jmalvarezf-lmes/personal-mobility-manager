"""
Infrastructure: iCal holiday parsing.

Parses `VEVENT` components from a fetched `.ics` payload into
`HolidayRecord`s, using the `icalendar` PyPI package (design.md D7). Split
into its own pure-function module sibling to
`google_calendar_provider.py`, mirroring the
`ambient_label_provider.py`/`ambient_label_parser.py` split.

Google's public Spain holiday calendar uses all-day `DATE` events for
`DTSTART` (e.g. `DTSTART;VALUE=DATE:20260101`), but this parser is
defensive about `DATETIME` events too (`DTSTART:20260106T000000Z`) since
nothing in the iCal spec guarantees a feed stays all-day forever. Events
missing a parsable `DTSTART` or `SUMMARY` are logged and skipped rather
than raising, matching this codebase's "skip and log, don't crash the
whole batch" convention (see `PostgresSerZoneRepository.list_all()`).

Filtering to genuine, city-applicable holidays (design.md D11): the
upstream feed mixes real public holidays with non-holiday "celebrations"
(Carnival, Father's Day, Easter Sunday, New Year's Eve, DST changes) as
ordinary `VEVENT`s indistinguishable by `SUMMARY` alone. The distinguishing
field is `DESCRIPTION`, evaluated per target city:
  - `DESCRIPTION == "Día festivo"` (exact) → a holiday for every city.
  - `DESCRIPTION` starting with `"Celebración en "` → a holiday only for a
    city whose capitalized `city_code` appears as an exact entry in the
    comma-separated region list that follows (up to the first newline).
  - Anything else (a generic `"Celebración\nPara ocultar..."` with no
    region list at all) → not a holiday for any city.
`icalendar` fully unescapes/unfolds `DESCRIPTION` (escaped commas and `\\n`
sequences become real commas/newlines), so a plain string comparison and
split work directly on `str(component.get("DESCRIPTION"))` with no manual
unescaping needed.
"""

import logging
from datetime import date, datetime

from icalendar import Calendar

from mobility_manager.domain.value_objects.holiday_record import HolidayRecord

logger = logging.getLogger(__name__)

_NATIONAL_HOLIDAY_DESCRIPTION = "Día festivo"
_REGIONAL_CELEBRATION_PREFIX = "Celebración en "


def parse_ical_holidays(ics_text: str, city_code: str) -> list[HolidayRecord]:
    """
    Parse `VEVENT` components from `ics_text` into a list of `HolidayRecord`,
    filtered to only those events that are genuine public holidays for
    `city_code` (see module docstring for the filtering rule).
    """
    calendar = Calendar.from_ical(ics_text)

    records: list[HolidayRecord] = []
    for component in calendar.walk("VEVENT"):
        dtstart = component.get("DTSTART")
        summary = component.get("SUMMARY")

        if dtstart is None or summary is None:
            logger.warning("Skipping VEVENT with missing DTSTART or SUMMARY")
            continue

        event_date = _extract_date(dtstart.dt)
        if event_date is None:
            logger.warning("Skipping VEVENT with unparsable DTSTART value: %r", dtstart.dt)
            continue

        if not _is_holiday_for_city(component.get("DESCRIPTION"), city_code):
            continue

        records.append(HolidayRecord(date=event_date, name=str(summary)))

    return records


def _is_holiday_for_city(description: object, city_code: str) -> bool:
    """
    Classify a `VEVENT`'s `DESCRIPTION` as a genuine holiday for `city_code`.

    See module docstring for the exact filtering rule (design.md D11).
    """
    if description is None:
        return False

    description_text = str(description)

    if description_text == _NATIONAL_HOLIDAY_DESCRIPTION:
        return True

    if description_text.startswith(_REGIONAL_CELEBRATION_PREFIX):
        return city_code.capitalize() in _regional_entries(description_text)

    return False


def _regional_entries(description_text: str) -> list[str]:
    """Extract the comma-separated region list from a `"Celebración en ..."` description."""
    region_list_line = description_text.split("\n", 1)[0]
    region_list_text = region_list_line[len(_REGIONAL_CELEBRATION_PREFIX) :]
    return [entry.strip() for entry in region_list_text.split(",")]


def _extract_date(value: object) -> date | None:
    """Return the calendar date from a DTSTART value, handling both DATE and DATETIME."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None
