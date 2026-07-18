"""
Domain: HolidayRecord value object.

Carries one parsed public holiday (date + name) from a PublicHolidayProvider,
before it is upserted into the per-city `holidays` table. Mirrors the
SerZoneBoundaryRecord convention of a plain ingestion-time record — see
add-ser-enforcement-calendar design.md D7.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class HolidayRecord:
    """Immutable record of one parsed public holiday."""

    date: date
    name: str
