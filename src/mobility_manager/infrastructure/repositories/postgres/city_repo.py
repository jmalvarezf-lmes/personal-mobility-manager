"""
Infrastructure: PostgresCityRepository.

Reads the `cities` table — the single live source of truth for which city
codes are registered. Shared by GET /cities and GET /parking/ser-zones'
city validation (see design.md D6/D7 of add-vehicle-ser-parking-exemption).
"""

from sqlalchemy import select
from sqlalchemy.engine import Engine

from mobility_manager.domain.entities.city import City
from mobility_manager.domain.ports.city_repository import CityRepository
from mobility_manager.infrastructure.orm.tables import cities_table


class PostgresCityRepository(CityRepository):
    """PostgreSQL-backed cities repository using SQLAlchemy Core."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def list_all(self) -> list[City]:
        """Return every row currently in the `cities` table, ordered by code."""
        with self._engine.connect() as conn:
            rows = conn.execute(select(cities_table).order_by(cities_table.c.code)).fetchall()
        return [City(code=row.code, name=row.name) for row in rows]
