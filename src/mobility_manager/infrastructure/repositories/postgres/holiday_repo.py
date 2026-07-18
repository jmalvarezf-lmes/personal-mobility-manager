"""
Infrastructure: PostgresHolidayRepository.

Persists per-city public holidays. The automated refresh job (RefreshPublicHolidays
-- see design.md D7/D8) only ever upserts `source='ical_national'` rows and
never touches `source='manual'` rows (regional/local holidays entered by
hand) -- see design.md D3.
"""

import logging

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from mobility_manager.domain.ports.holiday_repository import HolidayRepository
from mobility_manager.domain.value_objects.holiday_record import HolidayRecord
from mobility_manager.infrastructure.orm.tables import holidays_table

logger = logging.getLogger(__name__)

_ICAL_NATIONAL_SOURCE = "ical_national"


class PostgresHolidayRepository(HolidayRepository):
    """PostgreSQL-backed holiday repository using SQLAlchemy Core."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def upsert_national_holidays(self, city_code: str, holidays: list[HolidayRecord]) -> None:
        """
        Insert or update `source='ical_national'` rows for `city_code`.

        `ON CONFLICT (city_code, date, source) DO UPDATE SET name` -- never
        touches `source='manual'` rows, and never issues a blanket delete
        (see design.md D3). A no-op if `holidays` is empty.
        """
        if not holidays:
            return

        rows = [
            {
                "city_code": city_code,
                "date": h.date,
                "name": h.name,
                "source": _ICAL_NATIONAL_SOURCE,
            }
            for h in holidays
        ]

        stmt = insert(holidays_table)
        stmt = stmt.on_conflict_do_update(
            index_elements=["city_code", "date", "source"],
            set_={"name": stmt.excluded.name},
        )
        with self._engine.begin() as conn:
            conn.execute(stmt, rows)

    def has_no_national_holidays(self, city_code: str) -> bool:
        """
        Return True if `city_code` has zero `source='ical_national'` rows in
        `holidays`.

        Used by the refresh scheduler's startup-conditional immediate fetch
        (design.md D8): a cold/empty table fires immediately instead of
        waiting for the next interval tick.
        """
        query = text("SELECT 1 FROM holidays WHERE city_code = :city_code AND source = :source LIMIT 1")
        with self._engine.connect() as conn:
            row = conn.execute(query, {"city_code": city_code, "source": _ICAL_NATIONAL_SOURCE}).fetchone()
        return row is None
