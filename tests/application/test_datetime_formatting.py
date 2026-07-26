"""
Unit tests for application.datetime_formatting.format_local_datetime.

Covers: known-timezone conversion, None fallback to UTC, and an
unrecognized-string fallback to UTC.
"""

from datetime import UTC, datetime

from mobility_manager.application.datetime_formatting import format_local_datetime


def test_converts_to_a_known_timezone() -> None:
    dt = datetime(2026, 7, 26, 10, 0, tzinfo=UTC)

    result = format_local_datetime(dt, "Europe/Madrid")

    # Europe/Madrid is UTC+2 in July (CEST).
    assert result == "2026-07-26 12:00 CEST"


def test_falls_back_to_utc_when_timezone_is_none() -> None:
    dt = datetime(2026, 7, 26, 10, 0, tzinfo=UTC)

    result = format_local_datetime(dt, None)

    assert result == "2026-07-26 10:00 UTC"


def test_falls_back_to_utc_for_unrecognized_timezone_string() -> None:
    dt = datetime(2026, 7, 26, 10, 0, tzinfo=UTC)

    result = format_local_datetime(dt, "Not/AZone")

    assert result == "2026-07-26 10:00 UTC"
