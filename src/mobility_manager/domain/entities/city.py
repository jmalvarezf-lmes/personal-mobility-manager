"""
Domain entity: City.

Represents one row of the `cities` table — the shared reference dimension
for every city-scoped table in the system (see add-ser-enforcement-calendar
design.md D10 and the city-registry capability).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class City:
    """A registered city."""

    code: str
    name: str
