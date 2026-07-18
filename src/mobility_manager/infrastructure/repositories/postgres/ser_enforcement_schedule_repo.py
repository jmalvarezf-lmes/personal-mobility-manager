"""
Infrastructure: PostgresSerEnforcementSchedule.

Evaluates SER enforcement status per design.md D4's precedence order:
1. Sunday -> not active (absolute).
2. Holiday for city_code -> not active (absolute; absence of a `holidays`
   row is treated as "not a holiday" -- fails open, see design.md risks).
3. `fixed_date` exception matching today's month-day -> use its hours.
4. `month` exception matching today's month -> use its hours.
5. Otherwise -> use today's `ser_timetable_weekday_hours` row (respecting
   its `active` flag).

Uses SQLAlchemy Core with named-param text() queries, matching
PostgresSerZoneRepository's style.
"""

import logging
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.engine import Engine

from mobility_manager.domain.ports.ser_enforcement_schedule import SerEnforcementSchedule

logger = logging.getLogger(__name__)

# Hardcoded timezone used wherever "now" is evaluated for the enforcement
# check (design.md D9). This is an implementation detail of how this
# Postgres-backed evaluator computes "now", not part of the abstract port's
# contract — not stored in the `cities` table and not exposed as a setting
# in this change, a placeholder for a future per-user/per-city preference.
ENFORCEMENT_TIMEZONE = ZoneInfo("Europe/Madrid")


class PostgresSerEnforcementSchedule(SerEnforcementSchedule):
    """PostgreSQL-backed SER enforcement schedule evaluator."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def is_active_now(self, city_code: str) -> bool:
        """Evaluate enforcement status for `city_code` at datetime.now(ENFORCEMENT_TIMEZONE)."""
        now = datetime.now(ENFORCEMENT_TIMEZONE)
        weekday = now.weekday()  # 0=Monday..6=Sunday -- matches ser_timetable_weekday_hours
        current_time = now.time()

        # 1. Sunday is absolute -- wins over any exception match.
        if weekday == 6:
            return False

        # 2. Holiday is absolute -- wins over any exception match. Missing
        # data (no row) fails open: proceed as if not a holiday.
        if self._is_holiday(city_code, now.date()):
            return False

        # 3. fixed_date exception takes precedence over 4. month exception.
        month_day = now.strftime("%m-%d")
        fixed_date_hours = self._get_fixed_date_exception_hours(city_code, month_day)
        if fixed_date_hours is not None:
            start_time, end_time = fixed_date_hours
            return start_time <= current_time <= end_time

        month_hours = self._get_month_exception_hours(city_code, now.month)
        if month_hours is not None:
            start_time, end_time = month_hours
            return start_time <= current_time <= end_time

        # 5. Fall back to the weekday's base hours.
        weekday_hours = self._get_weekday_hours(city_code, weekday)
        if weekday_hours is None:
            logger.warning(
                "No ser_timetable_weekday_hours row for city_code=%r weekday=%r -- treating as not active",
                city_code,
                weekday,
            )
            return False
        active, start_time, end_time = weekday_hours
        if not active:
            return False
        return start_time <= current_time <= end_time

    def _is_holiday(self, city_code: str, today: date) -> bool:
        query = text("SELECT 1 FROM holidays WHERE city_code = :city_code AND date = :today LIMIT 1")
        with self._engine.connect() as conn:
            row = conn.execute(query, {"city_code": city_code, "today": today}).fetchone()
        return row is not None

    def _get_fixed_date_exception_hours(self, city_code: str, month_day: str) -> tuple[time, time] | None:
        query = text(
            "SELECT start_time, end_time FROM ser_timetable_exception "
            "WHERE city_code = :city_code AND recurrence = 'fixed_date' AND month_day = :month_day "
            "LIMIT 1"
        )
        with self._engine.connect() as conn:
            row = conn.execute(query, {"city_code": city_code, "month_day": month_day}).fetchone()
        if row is None:
            return None
        return row[0], row[1]

    def _get_month_exception_hours(self, city_code: str, month: int) -> tuple[time, time] | None:
        query = text(
            "SELECT start_time, end_time FROM ser_timetable_exception "
            "WHERE city_code = :city_code AND recurrence = 'month' AND month = :month "
            "LIMIT 1"
        )
        with self._engine.connect() as conn:
            row = conn.execute(query, {"city_code": city_code, "month": month}).fetchone()
        if row is None:
            return None
        return row[0], row[1]

    def _get_weekday_hours(self, city_code: str, weekday: int) -> tuple[bool, time, time] | None:
        query = text(
            "SELECT active, start_time, end_time FROM ser_timetable_weekday_hours "
            "WHERE city_code = :city_code AND weekday = :weekday"
        )
        with self._engine.connect() as conn:
            row = conn.execute(query, {"city_code": city_code, "weekday": weekday}).fetchone()
        if row is None:
            return None
        return row[0], row[1], row[2]
