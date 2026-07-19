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
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.ports.ser_zone_repository import SerZoneRepository
from mobility_manager.domain.value_objects.location import GeoLocation, _wgs84_to_utm
from mobility_manager.domain.value_objects.zone_area import ZoneArea
from mobility_manager.infrastructure.orm.tables import (
    ser_zone_areas_table,
    ser_zone_streets_table,
    ser_zones_table,
)

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
            "SELECT city_code, zone_number, zone_type, district, spot_count, geometry_wkt "
            "FROM ser_zones ORDER BY zone_number, zone_type"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query).fetchall()

        zones: list[SerZone] = []
        for row in rows:
            try:
                geometry = shapely_wkt.loads(row[5])
            except Exception:
                logger.warning(
                    "Skipping SER zone with unparsable geometry_wkt: zone_number=%r zone_type=%r",
                    row[1],
                    row[2],
                )
                continue
            zones.append(
                SerZone(
                    city_code=row[0],
                    zone_number=row[1],
                    zone_type=row[2],
                    district=row[3],
                    spot_count=row[4],
                    geometry=geometry,
                )
            )
        return zones

    def list_zones_for_city(self, city_code: str) -> list[SerZone]:
        """
        Return SER zones scoped to `city_code` only, ordered by zone_number.

        Mirrors list_all()'s corrupt-geometry skip behavior, but adds a
        WHERE city_code clause — see design.md D7 of
        add-vehicle-ser-parking-exemption.
        """
        query = text(
            "SELECT city_code, zone_number, zone_type, district, spot_count, geometry_wkt "
            "FROM ser_zones WHERE city_code = :city_code ORDER BY zone_number, zone_type"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query, {"city_code": city_code}).fetchall()

        zones: list[SerZone] = []
        for row in rows:
            try:
                geometry = shapely_wkt.loads(row[5])
            except Exception:
                logger.warning(
                    "Skipping SER zone with unparsable geometry_wkt: zone_number=%r zone_type=%r",
                    row[1],
                    row[2],
                )
                continue
            zones.append(
                SerZone(
                    city_code=row[0],
                    zone_number=row[1],
                    zone_type=row[2],
                    district=row[3],
                    spot_count=row[4],
                    geometry=geometry,
                )
            )
        return zones

    def get_street_names(self, city_code: str, zone_number: str, zone_type: str) -> list[str]:
        """Return all street names for the given (city_code, zone_number, zone_type)."""
        query = text(
            "SELECT street_name FROM ser_zone_streets "
            "WHERE city_code = :city_code AND zone_number = :zone_number AND zone_type = :zone_type "
            "ORDER BY street_name"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(
                query, {"city_code": city_code, "zone_number": zone_number, "zone_type": zone_type}
            ).fetchall()
        return [row[0] for row in rows]

    def get_zone_area(self, city_code: str, zone_number: str) -> ZoneArea | None:
        """Return the frontier for the given (city_code, zone_number), or None if absent."""
        query = text(
            "SELECT city_code, zone_number, neighbourhood, geometry_wkt FROM ser_zone_areas "
            "WHERE city_code = :city_code AND zone_number = :zone_number"
        )
        with self._engine.connect() as conn:
            row = conn.execute(query, {"city_code": city_code, "zone_number": zone_number}).fetchone()

        if row is None:
            return None

        try:
            geometry = shapely_wkt.loads(row[3])
        except Exception:
            logger.warning(
                "Skipping ser_zone_areas row with unparsable geometry_wkt: city_code=%r zone_number=%r",
                row[0],
                row[1],
            )
            return None

        return ZoneArea(city_code=row[0], zone_number=row[1], neighbourhood=row[2], geometry=geometry)

    def list_zone_areas(self) -> list[ZoneArea]:
        """Return all stored frontiers (across all cities) ordered by city_code, zone_number."""
        query = text(
            "SELECT city_code, zone_number, neighbourhood, geometry_wkt "
            "FROM ser_zone_areas ORDER BY city_code, zone_number"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query).fetchall()

        zone_areas: list[ZoneArea] = []
        for row in rows:
            try:
                geometry = shapely_wkt.loads(row[3])
            except Exception:
                logger.warning(
                    "Skipping ser_zone_areas row with unparsable geometry_wkt: city_code=%r zone_number=%r",
                    row[0],
                    row[1],
                )
                continue
            zone_areas.append(ZoneArea(city_code=row[0], zone_number=row[1], neighbourhood=row[2], geometry=geometry))
        return zone_areas

    def list_zone_areas_for_city(self, city_code: str) -> list[ZoneArea]:
        """Return frontiers scoped to `city_code` only, ordered by zone_number."""
        query = text(
            "SELECT city_code, zone_number, neighbourhood, geometry_wkt "
            "FROM ser_zone_areas WHERE city_code = :city_code ORDER BY zone_number"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query, {"city_code": city_code}).fetchall()

        zone_areas: list[ZoneArea] = []
        for row in rows:
            try:
                geometry = shapely_wkt.loads(row[3])
            except Exception:
                logger.warning(
                    "Skipping ser_zone_areas row with unparsable geometry_wkt: city_code=%r zone_number=%r",
                    row[0],
                    row[1],
                )
                continue
            zone_areas.append(ZoneArea(city_code=row[0], zone_number=row[1], neighbourhood=row[2], geometry=geometry))
        return zone_areas

    def bulk_replace(self, records: list[dict[str, Any]], zone_areas: list[dict[str, Any]] | None = None) -> int:
        """
        Replace one city's SER zone records (street names) and refresh its
        zone frontiers (ser_zone_areas) in a single transaction.

        ser_zones/ser_zone_streets: deletes existing rows for the ingesting
        city only (scoped DELETE, not a bare TRUNCATE — see design.md D6)
        and inserts all fresh records.

        ser_zone_areas: NOT delete-then-insert. `vehicle_ser_parking_exemptions`
        holds a composite FK to `(city_code, zone_number)` on this table
        (see add-vehicle-ser-parking-exemption design.md), so a blanket
        delete-then-reinsert would either abort the whole ingestion run
        (FK violation, no `ON DELETE` action) or — if the FK were simply
        made `CASCADE` — silently wipe every vehicle's saved exemption on
        every scheduled re-ingestion, even when the same zone_number is
        re-ingested unchanged. Instead:
        - Every `zone_area_rows` entry is upserted (`INSERT ... ON CONFLICT
          (city_code, zone_number) DO UPDATE`), so a `zone_number` that is
          still present in the fresh data is never deleted and any
          exemption referencing it is left completely undisturbed, even
          though its `neighbourhood`/`geometry_wkt` get refreshed.
        - Only rows whose `zone_number` is NOT present in the fresh
          `zone_area_rows` for this city (i.e. genuinely retired zones) are
          deleted — via the `ser_zone_areas_table` Core `.delete().where()`
          construct — and that deletion is allowed to cascade into
          `vehicle_ser_parking_exemptions` (see the paired Alembic
          migration adding `ondelete="CASCADE"` to that FK), which is
          correct: an exemption pointing at a zone that no longer resolves
          to a barrio is meaningless.
        - If `zone_area_rows` is empty for this ingestion run, all existing
          `ser_zone_areas` rows for the city are deleted (matching the
          prior/edge-case behavior — nothing to upsert or preserve).

        Returns the number of ser_zones rows inserted. Each record dict is
        expected to carry a "city_code" key and a "street_names" key
        (list[str]) in addition to the ser_zones columns. `zone_areas` is a
        list of dicts with "city_code", "zone_number", "neighbourhood",
        "geometry_wkt" keys — one per resolvable zone_number (see
        add-ser-zone-frontiers design.md D6).

        If `records` is empty, this is a no-op: there is no city_code to
        scope a delete to, matching the "zero parsed records aborts the run
        without mutating stored data" contract in the ser-zone-ingestion
        spec (IngestSerZones already raises before reaching this method in
        that case; this repo-level no-op is the safe fallback for any other
        caller).
        """
        zone_areas = zone_areas or []

        if not records:
            return 0

        city_code = records[0]["city_code"]

        zone_rows = [
            {
                "city_code": r["city_code"],
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
                "city_code": r["city_code"],
                "zone_number": r["zone_number"],
                "zone_type": r["zone_type"],
                "street_name": street_name,
            }
            for r in records
            for street_name in r.get("street_names", [])
        ]

        zone_area_rows = [
            {
                "city_code": za["city_code"],
                "zone_number": za["zone_number"],
                "neighbourhood": za["neighbourhood"],
                "geometry_wkt": za["geometry_wkt"],
            }
            for za in zone_areas
        ]

        with self._engine.begin() as conn:
            conn.execute(text("DELETE FROM ser_zones WHERE city_code = :city_code"), {"city_code": city_code})
            conn.execute(
                text("DELETE FROM ser_zone_streets WHERE city_code = :city_code"), {"city_code": city_code}
            )
            conn.execute(ser_zones_table.insert(), zone_rows)
            if street_rows:
                conn.execute(ser_zone_streets_table.insert(), street_rows)

            if zone_area_rows:
                upsert_stmt = insert(ser_zone_areas_table).values(zone_area_rows)
                upsert_stmt = upsert_stmt.on_conflict_do_update(
                    index_elements=["city_code", "zone_number"],
                    set_={
                        "neighbourhood": upsert_stmt.excluded.neighbourhood,
                        "geometry_wkt": upsert_stmt.excluded.geometry_wkt,
                    },
                )
                conn.execute(upsert_stmt)

                fresh_zone_numbers = [za["zone_number"] for za in zone_area_rows]
                conn.execute(
                    ser_zone_areas_table.delete().where(
                        ser_zone_areas_table.c.city_code == city_code,
                        ser_zone_areas_table.c.zone_number.notin_(fresh_zone_numbers),
                    )
                )
            else:
                conn.execute(ser_zone_areas_table.delete().where(ser_zone_areas_table.c.city_code == city_code))

        return len(zone_rows)
