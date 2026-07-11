"""
Infrastructure: PostgresSerZoneRepository.

No PostGIS: geometry is stored as WKT text (EPSG:25830). find_containing()
and find_nearest() load all zone rows via list_all() and run shapely checks
in Python — no SQL bounding-box prefilter, since the post-dissolve row count
is small (a few hundred). See design.md D5.
"""

import logging
from typing import Any

from shapely import wkt as shapely_wkt
from shapely.geometry import Point
from sqlalchemy import text
from sqlalchemy.engine import Engine

from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.ports.ser_zone_repository import SerZoneRepository
from mobility_manager.domain.value_objects.location import GeoLocation, _wgs84_to_utm
from mobility_manager.infrastructure.orm.tables import ser_zone_streets_table, ser_zones_table

logger = logging.getLogger(__name__)


class PostgresSerZoneRepository(SerZoneRepository):
    """PostgreSQL-backed SER zone repository using SQLAlchemy Core."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def find_nearest(self, location: GeoLocation) -> SerZone | None:
        """
        Find the nearest SER zone by distance to polygon geometry.

        Returns None if no zones are stored. Distance is zero if location
        falls inside a zone's polygon.
        """
        zones = self.list_all()
        if not zones:
            return None

        utm_x, utm_y = _wgs84_to_utm.transform(location.lng, location.lat)
        point = Point(utm_x, utm_y)

        return min(zones, key=lambda z: z.geometry.distance(point))

    def find_containing(self, location: GeoLocation) -> SerZone | None:
        """Return the first stored zone whose polygon contains the location, or None."""
        for zone in self.list_all():
            if zone.contains(location):
                return zone
        return None

    def list_all(self) -> list[SerZone]:
        """
        Return all SER zones ordered by zone_number.

        A row whose geometry_wkt fails to parse is logged and skipped rather
        than raising, so one corrupt row does not take down every caller
        (find_nearest, find_containing, and the bulk GET /parking/ser-zones
        endpoint all depend on this method).
        """
        query = text(
            "SELECT zone_number, zone_type, district, spot_count, geometry_wkt "
            "FROM ser_zones ORDER BY zone_number, zone_type"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query).fetchall()

        zones: list[SerZone] = []
        for row in rows:
            try:
                geometry = shapely_wkt.loads(row[4])
            except Exception:
                logger.warning(
                    "Skipping SER zone with unparsable geometry_wkt: zone_number=%r zone_type=%r",
                    row[0],
                    row[1],
                )
                continue
            zones.append(
                SerZone(
                    zone_number=row[0],
                    zone_type=row[1],
                    district=row[2],
                    spot_count=row[3],
                    geometry=geometry,
                )
            )
        return zones

    def get_street_names(self, zone_number: str, zone_type: str) -> list[str]:
        """Return all street names for the given (zone_number, zone_type)."""
        query = text(
            "SELECT street_name FROM ser_zone_streets "
            "WHERE zone_number = :zone_number AND zone_type = :zone_type "
            "ORDER BY street_name"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query, {"zone_number": zone_number, "zone_type": zone_type}).fetchall()
        return [row[0] for row in rows]

    def bulk_replace(self, records: list[dict[str, Any]]) -> int:
        """
        Replace all SER zone records (and their street names) in a single transaction.

        Truncates both ser_zones and ser_zone_streets and inserts all
        records; returns the number of ser_zones rows inserted. Each record
        dict is expected to carry a "street_names" key (list[str]) in
        addition to the ser_zones columns.
        """
        if not records:
            with self._engine.begin() as conn:
                conn.execute(text("TRUNCATE ser_zones"))
                conn.execute(text("TRUNCATE ser_zone_streets"))
            return 0

        zone_rows = [
            {
                "zone_number": r["zone_number"],
                "zone_type": r["zone_type"],
                "district": r["district"],
                "spot_count": r["spot_count"],
                "geometry_wkt": r["geometry_wkt"],
            }
            for r in records
        ]

        street_rows = [
            {
                "zone_number": r["zone_number"],
                "zone_type": r["zone_type"],
                "street_name": street_name,
            }
            for r in records
            for street_name in r.get("street_names", [])
        ]

        with self._engine.begin() as conn:
            conn.execute(text("TRUNCATE ser_zones"))
            conn.execute(text("TRUNCATE ser_zone_streets"))
            conn.execute(ser_zones_table.insert(), zone_rows)
            if street_rows:
                conn.execute(ser_zone_streets_table.insert(), street_rows)

        return len(zone_rows)
