"""
Infrastructure: PostgresSerZoneRepository.

Implements SerZoneRepository using PostgreSQL with SQLAlchemy Core.
Uses bounding-box SQL filter + Haversine Python sort for nearest zone lookup.
Uses truncate-reload strategy for bulk ingestion.
"""
import math

from sqlalchemy import Column, Float, Integer, MetaData, Table, Text, text
from sqlalchemy.engine import Engine

from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.ports.ser_zone_repository import SerZoneRepository
from mobility_manager.domain.value_objects.location import GeoLocation

metadata = MetaData()

ser_zones_table = Table(
    "ser_zones",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("street_name", Text, nullable=False),
    Column("zone_code", Text, nullable=False),
    Column("zone_label", Text, nullable=False),
    Column("latitude", Float, nullable=False),
    Column("longitude", Float, nullable=False),
)


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Compute the great-circle distance in metres between two WGS84 points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(a))


class PostgresSerZoneRepository(SerZoneRepository):
    """PostgreSQL-backed SER zone repository using SQLAlchemy Core."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def find_nearest(
        self,
        location: GeoLocation,
        radius_deg: float = 0.01,
    ) -> SerZone | None:
        """
        Find the nearest SER zone within radius_deg degrees.

        First queries with the given radius; doubles the radius once if no
        results are returned.
        """
        result = self._query_bbox(location, radius_deg)
        if not result:
            result = self._query_bbox(location, radius_deg * 2)
        if not result:
            return None

        # Sort by Haversine distance and return the closest
        result.sort(key=lambda r: _haversine_m(location.lat, location.lng, r[0], r[1]))
        best = result[0]
        return SerZone(
            street_name=best[2],
            zone_code=best[3],
            zone_label=best[4],
            location=GeoLocation(lat=best[0], lng=best[1]),
        )

    def _query_bbox(
        self,
        location: GeoLocation,
        radius_deg: float,
    ) -> list[tuple[float, float, str, str, str]]:
        """Execute bounding-box query and return list of (lat, lng, street, code, label)."""
        lat, lng = location.lat, location.lng
        query = text(
            """
            SELECT latitude, longitude, street_name, zone_code, zone_label
            FROM ser_zones
            WHERE latitude  BETWEEN :lat_min  AND :lat_max
              AND longitude BETWEEN :lng_min  AND :lng_max
            """
        )
        params = {
            "lat_min": lat - radius_deg,
            "lat_max": lat + radius_deg,
            "lng_min": lng - radius_deg,
            "lng_max": lng + radius_deg,
        }
        with self._engine.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [(r[0], r[1], r[2], r[3], r[4]) for r in rows]

    def bulk_replace(self, records: list[dict]) -> int:
        """
        Replace all SER zone records in a single transaction.

        Truncates the table and inserts all records; returns the number of
        records inserted.
        """
        if not records:
            with self._engine.begin() as conn:
                conn.execute(text("TRUNCATE ser_zones"))
            return 0

        with self._engine.begin() as conn:
            conn.execute(text("TRUNCATE ser_zones"))
            conn.execute(ser_zones_table.insert(), records)

        return len(records)
