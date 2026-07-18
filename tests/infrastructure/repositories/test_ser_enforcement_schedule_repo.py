"""
Unit tests for PostgresSerEnforcementSchedule.is_active_now().

Uses a mocked SQLAlchemy Engine/Connection (no live Postgres, mirroring
test_ser_zone_repo.py's convention) whose execute() dispatches on the query
text to return the row appropriate for each of the four private lookups
(_is_holiday, _get_fixed_date_exception_hours, _get_month_exception_hours,
_get_weekday_hours). "Now" is frozen by monkeypatching the module's
`datetime` class with a fixed .now() classmethod, since is_active_now()
evaluates datetime.now(ENFORCEMENT_TIMEZONE) directly and there is no
separately-factored pure evaluation function to test in isolation — see
add-ser-enforcement-calendar tasks.md 8.2 and design.md D4.

Covers every scenario in specs/ser-enforcement-schedule/spec.md.
"""

from datetime import datetime, time
from unittest.mock import MagicMock

import pytest

from mobility_manager.infrastructure.repositories.postgres import (
    ser_enforcement_schedule_repo as repo_module,
)
from mobility_manager.infrastructure.repositories.postgres.ser_enforcement_schedule_repo import (
    ENFORCEMENT_TIMEZONE,
    PostgresSerEnforcementSchedule,
)


def _make_engine(
    *,
    holiday_row: tuple | None = None,
    fixed_date_row: tuple[time, time] | None = None,
    month_row: tuple[time, time] | None = None,
    weekday_row: tuple[bool, time, time] | None = None,
) -> MagicMock:
    """
    Build a mocked Engine whose connect().execute(query, params).fetchone()
    dispatches based on the query's SQL text, so each of the four private
    lookups in PostgresSerEnforcementSchedule can be independently
    controlled per test.
    """
    engine = MagicMock()
    conn = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn

    def _execute(query: object, params: dict | None = None) -> MagicMock:
        sql = str(query)
        result = MagicMock()
        if "FROM holidays" in sql:
            result.fetchone.return_value = holiday_row
        elif "recurrence = 'fixed_date'" in sql:
            result.fetchone.return_value = fixed_date_row
        elif "recurrence = 'month'" in sql:
            result.fetchone.return_value = month_row
        elif "FROM ser_timetable_weekday_hours" in sql:
            result.fetchone.return_value = weekday_row
        else:
            raise AssertionError(f"Unexpected query in test: {sql!r}")
        return result

    conn.execute.side_effect = _execute
    return engine


def _freeze_now(monkeypatch: pytest.MonkeyPatch, frozen: datetime) -> None:
    """Monkeypatch the module's `datetime` class so `datetime.now(tz)` returns `frozen`."""

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:  # noqa: ARG003 - tz ignored, frozen already carries tzinfo
            return frozen

    monkeypatch.setattr(repo_module, "datetime", _FrozenDateTime)


# ---------------------------------------------------------------------------
# Weekday hours (Mon-Fri normal hours)
# ---------------------------------------------------------------------------


def test_weekday_within_normal_hours_is_active(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wednesday 14:00 Europe/Madrid, no holiday/exception -> True (09:00-21:00 window)."""
    _freeze_now(monkeypatch, datetime(2026, 7, 15, 14, 0, tzinfo=ENFORCEMENT_TIMEZONE))  # Wednesday
    engine = _make_engine(
        holiday_row=None,
        fixed_date_row=None,
        month_row=None,
        weekday_row=(True, time(9, 0), time(21, 0)),
    )
    schedule = PostgresSerEnforcementSchedule(engine)

    assert schedule.is_active_now("madrid") is True


def test_weekday_outside_normal_hours_is_not_active(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wednesday 22:00 Europe/Madrid -> False (past the 09:00-21:00 window)."""
    _freeze_now(monkeypatch, datetime(2026, 7, 15, 22, 0, tzinfo=ENFORCEMENT_TIMEZONE))  # Wednesday
    engine = _make_engine(
        holiday_row=None,
        fixed_date_row=None,
        month_row=None,
        weekday_row=(True, time(9, 0), time(21, 0)),
    )
    schedule = PostgresSerEnforcementSchedule(engine)

    assert schedule.is_active_now("madrid") is False


# ---------------------------------------------------------------------------
# Saturday reduced hours
# ---------------------------------------------------------------------------


def test_saturday_within_reduced_hours_is_active(monkeypatch: pytest.MonkeyPatch) -> None:
    """Saturday 14:00 -> True (09:00-15:00 window), no matching exception."""
    _freeze_now(monkeypatch, datetime(2026, 7, 18, 14, 0, tzinfo=ENFORCEMENT_TIMEZONE))  # Saturday
    engine = _make_engine(
        holiday_row=None,
        fixed_date_row=None,
        month_row=None,
        weekday_row=(True, time(9, 0), time(15, 0)),
    )
    schedule = PostgresSerEnforcementSchedule(engine)

    assert schedule.is_active_now("madrid") is True


def test_saturday_outside_reduced_hours_is_not_active(monkeypatch: pytest.MonkeyPatch) -> None:
    """Saturday 16:00 -> False (past the 09:00-15:00 window)."""
    _freeze_now(monkeypatch, datetime(2026, 7, 18, 16, 0, tzinfo=ENFORCEMENT_TIMEZONE))  # Saturday
    engine = _make_engine(
        holiday_row=None,
        fixed_date_row=None,
        month_row=None,
        weekday_row=(True, time(9, 0), time(15, 0)),
    )
    schedule = PostgresSerEnforcementSchedule(engine)

    assert schedule.is_active_now("madrid") is False


# ---------------------------------------------------------------------------
# Sunday: absolute, overrides any exception match
# ---------------------------------------------------------------------------


def test_sunday_is_never_active_even_matching_a_fixed_date_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sunday, even one whose date also matches a fixed_date exception -> always False."""
    _freeze_now(monkeypatch, datetime(2026, 7, 19, 14, 0, tzinfo=ENFORCEMENT_TIMEZONE))  # Sunday
    engine = _make_engine(
        holiday_row=None,
        # Even if a fixed_date exception would otherwise match and allow 14:00...
        fixed_date_row=(time(9, 0), time(15, 0)),
        month_row=None,
        weekday_row=(False, time(9, 0), time(15, 0)),
    )
    schedule = PostgresSerEnforcementSchedule(engine)

    assert schedule.is_active_now("madrid") is False


# ---------------------------------------------------------------------------
# Holiday: absolute, overrides any exception match
# ---------------------------------------------------------------------------


def test_holiday_is_never_active_even_matching_an_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """A date with a matching holidays row -> always False, even matching a fixed_date/month exception."""
    _freeze_now(monkeypatch, datetime(2026, 7, 15, 14, 0, tzinfo=ENFORCEMENT_TIMEZONE))  # Wednesday
    engine = _make_engine(
        holiday_row=(1,),  # a matching holidays row exists
        fixed_date_row=(time(9, 0), time(15, 0)),  # would otherwise match and allow 14:00
        month_row=None,
        weekday_row=(True, time(9, 0), time(21, 0)),
    )
    schedule = PostgresSerEnforcementSchedule(engine)

    assert schedule.is_active_now("madrid") is False


# ---------------------------------------------------------------------------
# August month exception
# ---------------------------------------------------------------------------


def test_august_non_holiday_weekday_applies_reduced_hours_within_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-holiday Tuesday in August at 14:00 -> True (August exception's 09:00-15:00 window)."""
    _freeze_now(monkeypatch, datetime(2026, 8, 11, 14, 0, tzinfo=ENFORCEMENT_TIMEZONE))  # Tuesday
    engine = _make_engine(
        holiday_row=None,
        fixed_date_row=None,
        month_row=(time(9, 0), time(15, 0)),
        weekday_row=(True, time(9, 0), time(21, 0)),  # normal weekday hours would allow 14:00-21:00 too
    )
    schedule = PostgresSerEnforcementSchedule(engine)

    assert schedule.is_active_now("madrid") is True


def test_august_non_holiday_weekday_outside_reduced_hours_is_not_active(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-holiday Tuesday in August at 16:00 -> False, even though normal weekday hours extend to 21:00."""
    _freeze_now(monkeypatch, datetime(2026, 8, 11, 16, 0, tzinfo=ENFORCEMENT_TIMEZONE))  # Tuesday
    engine = _make_engine(
        holiday_row=None,
        fixed_date_row=None,
        month_row=(time(9, 0), time(15, 0)),
        weekday_row=(True, time(9, 0), time(21, 0)),
    )
    schedule = PostgresSerEnforcementSchedule(engine)

    assert schedule.is_active_now("madrid") is False


def test_august_non_holiday_saturday_applies_reduced_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-holiday Saturday in August at 14:00 -> True (August exception, same 09:00-15:00 window as Saturday's own hours)."""
    _freeze_now(monkeypatch, datetime(2026, 8, 8, 14, 0, tzinfo=ENFORCEMENT_TIMEZONE))  # Saturday
    engine = _make_engine(
        holiday_row=None,
        fixed_date_row=None,
        month_row=(time(9, 0), time(15, 0)),
        weekday_row=(True, time(9, 0), time(15, 0)),
    )
    schedule = PostgresSerEnforcementSchedule(engine)

    assert schedule.is_active_now("madrid") is True


# ---------------------------------------------------------------------------
# Dec 24 / Dec 31 fixed-date exceptions
# ---------------------------------------------------------------------------


def test_dec_24_applies_reduced_hours_regardless_of_weekday(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dec 24 (a Thursday, non-Sunday, non-holiday) at 14:00 -> True, even though normal weekday hours extend to 21:00."""
    _freeze_now(monkeypatch, datetime(2026, 12, 24, 14, 0, tzinfo=ENFORCEMENT_TIMEZONE))  # Thursday
    engine = _make_engine(
        holiday_row=None,
        fixed_date_row=(time(9, 0), time(15, 0)),
        month_row=None,
        weekday_row=(True, time(9, 0), time(21, 0)),
    )
    schedule = PostgresSerEnforcementSchedule(engine)

    assert schedule.is_active_now("madrid") is True


def test_dec_31_applies_reduced_hours_regardless_of_weekday(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dec 31 (a Thursday, non-Sunday, non-holiday) at 14:00 -> True."""
    _freeze_now(monkeypatch, datetime(2026, 12, 31, 14, 0, tzinfo=ENFORCEMENT_TIMEZONE))  # Thursday
    engine = _make_engine(
        holiday_row=None,
        fixed_date_row=(time(9, 0), time(15, 0)),
        month_row=None,
        weekday_row=(True, time(9, 0), time(21, 0)),
    )
    schedule = PostgresSerEnforcementSchedule(engine)

    assert schedule.is_active_now("madrid") is True


def test_dec_24_outside_reduced_hours_is_not_active(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dec 24 at 20:00 -> False, even though normal weekday hours would otherwise extend to 21:00."""
    _freeze_now(monkeypatch, datetime(2026, 12, 24, 20, 0, tzinfo=ENFORCEMENT_TIMEZONE))  # Thursday
    engine = _make_engine(
        holiday_row=None,
        fixed_date_row=(time(9, 0), time(15, 0)),
        month_row=None,
        weekday_row=(True, time(9, 0), time(21, 0)),
    )
    schedule = PostgresSerEnforcementSchedule(engine)

    assert schedule.is_active_now("madrid") is False


# ---------------------------------------------------------------------------
# Fixed-date exception precedence over month exception
# ---------------------------------------------------------------------------


def test_fixed_date_exception_takes_precedence_over_month_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    When both a fixed_date and a month exception would match the same date,
    the fixed_date exception's hours are used. Proven by giving each a
    contradictory answer at the same instant: fixed_date's window (09:00-21:00)
    would return True at 20:00; month's window (09:00-15:00) would return
    False at 20:00. The actual result must be True, proving fixed_date won.
    """
    _freeze_now(monkeypatch, datetime(2026, 8, 24, 20, 0, tzinfo=ENFORCEMENT_TIMEZONE))  # Monday in August
    engine = _make_engine(
        holiday_row=None,
        fixed_date_row=(time(9, 0), time(21, 0)),
        month_row=(time(9, 0), time(15, 0)),
        weekday_row=(True, time(9, 0), time(21, 0)),
    )
    schedule = PostgresSerEnforcementSchedule(engine)

    assert schedule.is_active_now("madrid") is True


# ---------------------------------------------------------------------------
# Missing holiday data fails open
# ---------------------------------------------------------------------------


def test_missing_holiday_data_fails_open_and_proceeds_to_weekday_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    No matching holidays row (e.g. feed unreachable, stale, or city just
    onboarded) -> holiday check treated as not matching; evaluation proceeds
    to exception/weekday-hours steps rather than being suppressed.
    """
    _freeze_now(monkeypatch, datetime(2026, 7, 15, 14, 0, tzinfo=ENFORCEMENT_TIMEZONE))  # Wednesday
    engine = _make_engine(
        holiday_row=None,  # no data at all for this city/date
        fixed_date_row=None,
        month_row=None,
        weekday_row=(True, time(9, 0), time(21, 0)),
    )
    schedule = PostgresSerEnforcementSchedule(engine)

    assert schedule.is_active_now("madrid") is True


def test_missing_weekday_hours_row_treated_as_not_active(monkeypatch: pytest.MonkeyPatch) -> None:
    """No ser_timetable_weekday_hours row at all for this city/weekday -> not active (defensive fallback)."""
    _freeze_now(monkeypatch, datetime(2026, 7, 15, 14, 0, tzinfo=ENFORCEMENT_TIMEZONE))  # Wednesday
    engine = _make_engine(
        holiday_row=None,
        fixed_date_row=None,
        month_row=None,
        weekday_row=None,
    )
    schedule = PostgresSerEnforcementSchedule(engine)

    assert schedule.is_active_now("madrid") is False
