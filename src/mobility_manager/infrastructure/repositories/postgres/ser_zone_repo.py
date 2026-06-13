"""
Infrastructure: PostgresSerZoneRepository.

Uses UTM (EPSG:25830) Euclidean distance for maximum precision.
Bounding-box SQL filter on WGS84 lat/lng narrows candidates; final sort uses
Euclidean distance in UTM space — centimetre-accurate for the Madrid area.
"""
import math

from pyproj import Transformer
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
    Column("latitude", Float, nullable=False),   # WGS84 — bounding-box index
    Column("longitude", Float, nullable=False),  # WGS84 — bounding-box index
    Column("utm_x", Float, nullable=False),      # EPSG:25830 easting (metres)
    Column("utm_y", Float, nullable=False),      # EPSG:25830 northing (metres)
)

# WGS84 → EPSG:25830; always_xy=True means transform(lng, lat) → (easting, northing)
_wgs84_to_utm = Transformer.from_crs("EPSG:4326", "EPSG:25830", always_xy=True)


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Euclidean distance in metres between two WGS84 points via UTM Zone 30N."""
    x1, y1 = _wgs84_to_utm.transform(lng1, lat1)
    x2, y2 = _wgs84_to_utm.transform(lng2, lat2)
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


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

        Queries the bounding box; doubles the radius once if no results.
        Ranks candidates by Euclidean distance in UTM space.
        """
        result = self._query_bbox(location, radius_deg)
        if not result:
            result = self._query_bbox(location, radius_deg * 2)
        if not result:
            return None

        # Convert query location to UTM once for distance ranking.
        q_utm_x, q_utm_y = _wgs84_to_utm.transform(location.lng, location.lat)
        result.sort(
            key=lambda r: math.sqrt((r[2] - q_utm_x) ** 2 + (r[3] - q_utm_y) ** 2)
        )

        best = result[0]
        return SerZone(
            street_name=best[4],
            zone_code=best[5],
            zone_label=best[6],
            location=GeoLocation(lat=best[0], lng=best[1]),
        )

    def _query_bbox(
        self,
        location: GeoLocation,
        radius_deg: float,
    ) -> list[tuple[float, float, float, float, str, str, str]]:
        """Execute bounding-box query; returns (lat, lng, utm_x, utm_y, street, code, label)."""
        lat, lng = location.lat, location.lng
        query = text(
            """
            SELECT latitude, longitude, utm_x, utm_y, street_name, zone_code, zone_label
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
        return [(r[0], r[1], r[2], r[3], r[4], r[5], r[6]) for r in rows]

    def bulk_replace(self, records: list[dict]) -> int:
        """
        Replace all SER zone records in a single transaction.

        Truncates the table and inserts all records; returns the number inserted.
        """
        if not records:
            with self._engine.begin() as conn:
                conn.execute(text("TRUNCATE ser_zones"))
            return 0

        with self._engine.begin() as conn:
            conn.execute(text("TRUNCATE ser_zones"))
            conn.execute(ser_zones_table.insert(), records)

        return len(records)
