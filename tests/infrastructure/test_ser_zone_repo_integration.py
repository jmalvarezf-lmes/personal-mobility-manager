"""
Integration tests for PostgresSerZoneRepository.

These tests require a running PostgreSQL instance.
Set POSTGRES_DSN env var or skip tests if not available.
"""

import os

import pytest
from shapely.geometry import Polygon
from sqlalchemy import create_engine, text

from mobility_manager.domain.value_objects.location import GeoLocation
from mobility_manager.infrastructure.repositories.postgres.ser_zone_repo import (
    PostgresSerZoneRepository,
)

# Simple square polygons (EPSG:25830 metres) near Puerta del Sol, matching
# UTM coordinates used elsewhere in the test suite.
_SQUARE_A_WKT = "POLYGON((440584 4474459, 440604 4474459, 440604 4474479, 440584 4474479, 440584 4474459))"
_SQUARE_B_WKT = "POLYGON((441584 4475459, 441604 4475459, 441604 4475479, 441584 4475479, 441584 4475459))"


@pytest.fixture
def pg_engine():
    """Create a SQLAlchemy engine from POSTGRES_DSN env var, or skip if not set."""
    dsn = os.environ.get("POSTGRES_DSN")
    if not dsn:
        pytest.skip("POSTGRES_DSN environment variable not set — skipping integration test")
    engine = create_engine(dsn, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS ser_zones (
                    id             SERIAL PRIMARY KEY,
                    zone_number    VARCHAR(10) NOT NULL,
                    zone_type      VARCHAR(50) NOT NULL DEFAULT '',
                    district       TEXT NOT NULL DEFAULT '',
                    spot_count     INTEGER NOT NULL DEFAULT -1,
                    geometry_wkt   TEXT NOT NULL,
                    CONSTRAINT uq_ser_zones_zone_number_zone_type UNIQUE (zone_number, zone_type)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS ser_zone_streets (
                    id             SERIAL PRIMARY KEY,
                    zone_number    VARCHAR(10) NOT NULL,
                    zone_type      VARCHAR(50) NOT NULL,
                    street_name    TEXT NOT NULL
                )
                """
            )
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_ser_zone_streets_zone ON ser_zone_streets (zone_number, zone_type)")
        )
        conn.execute(text("TRUNCATE ser_zones"))
        conn.execute(text("TRUNCATE ser_zone_streets"))
    yield engine
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE ser_zones"))
        conn.execute(text("TRUNCATE ser_zone_streets"))
    engine.dispose()


def _make_zone_record(
    zone_number: str = "163",
    zone_type: str = "Azul",
    district: str = "CENTRO",
    spot_count: int = 15,
    geometry_wkt: str = _SQUARE_A_WKT,
    street_names: list[str] | None = None,
) -> dict:
    return {
        "zone_number": zone_number,
        "zone_type": zone_type,
        "district": district,
        "spot_count": spot_count,
        "geometry_wkt": geometry_wkt,
        "street_names": street_names if street_names is not None else ["ABADA"],
    }


def test_bulk_replace_and_find_containing(pg_engine) -> None:
    """Insert a record via bulk_replace, then find it via find_containing."""
    repo = PostgresSerZoneRepository(pg_engine)

    inserted = repo.bulk_replace([_make_zone_record()])
    assert inserted == 1

    square = Polygon([(440584, 4474459), (440604, 4474459), (440604, 4474479), (440584, 4474479)])
    centroid = square.centroid
    from pyproj import Transformer

    utm_to_wgs84 = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)
    lng, lat = utm_to_wgs84.transform(centroid.x, centroid.y)

    zone = repo.find_containing(GeoLocation(lat=lat, lng=lng))

    assert zone is not None
    assert zone.zone_number == "163"
    assert zone.zone_type == "Azul"
    assert zone.district == "CENTRO"
    assert zone.spot_count == 15


def test_find_containing_returns_none_when_outside_all_zones(pg_engine) -> None:
    repo = PostgresSerZoneRepository(pg_engine)
    repo.bulk_replace([_make_zone_record()])

    # Far outside Madrid entirely.
    zone = repo.find_containing(GeoLocation(lat=41.0, lng=-4.5))

    assert zone is None


def test_find_containing_returns_none_when_empty(pg_engine) -> None:
    repo = PostgresSerZoneRepository(pg_engine)
    repo.bulk_replace([])

    zone = repo.find_containing(GeoLocation(lat=40.4168, lng=-3.7038))

    assert zone is None


def test_find_nearest_returns_zero_distance_when_inside(pg_engine) -> None:
    repo = PostgresSerZoneRepository(pg_engine)
    repo.bulk_replace([_make_zone_record()])

    square = Polygon([(440584, 4474459), (440604, 4474459), (440604, 4474479), (440584, 4474479)])
    centroid = square.centroid
    from pyproj import Transformer

    utm_to_wgs84 = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)
    lng, lat = utm_to_wgs84.transform(centroid.x, centroid.y)

    location = GeoLocation(lat=lat, lng=lng)
    zone = repo.find_nearest(location)

    assert zone is not None
    assert zone.geometry.distance(centroid) == pytest.approx(0.0)


def test_find_nearest_returns_none_when_empty(pg_engine) -> None:
    """find_nearest returns None when the table is empty."""
    repo = PostgresSerZoneRepository(pg_engine)
    repo.bulk_replace([])

    location = GeoLocation(lat=40.4168, lng=-3.7038)
    zone = repo.find_nearest(location)

    assert zone is None


def test_find_nearest_picks_closest_of_two_zones(pg_engine) -> None:
    repo = PostgresSerZoneRepository(pg_engine)

    repo.bulk_replace(
        [
            _make_zone_record(zone_number="163", zone_type="Azul", geometry_wkt=_SQUARE_A_WKT),
            _make_zone_record(zone_number="200", zone_type="Verde", geometry_wkt=_SQUARE_B_WKT),
        ]
    )

    from pyproj import Transformer

    utm_to_wgs84 = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)
    # A point very close to square A's centroid.
    lng, lat = utm_to_wgs84.transform(440594.0, 4474469.0)

    zone = repo.find_nearest(GeoLocation(lat=lat, lng=lng))

    assert zone is not None
    assert zone.zone_number == "163"


def test_bulk_replace_truncates_old_records(pg_engine) -> None:
    """bulk_replace removes existing data before inserting new records."""
    repo = PostgresSerZoneRepository(pg_engine)

    repo.bulk_replace([_make_zone_record(zone_number="100", zone_type="Verde", geometry_wkt=_SQUARE_A_WKT)])
    repo.bulk_replace([_make_zone_record(zone_number="200", zone_type="Azul", geometry_wkt=_SQUARE_B_WKT)])

    zones = repo.list_all()

    assert len(zones) == 1
    assert zones[0].zone_number == "200"


def test_spot_count_minus_one_for_unknown(pg_engine) -> None:
    """Verify that spot_count=-1 round-trips correctly."""
    repo = PostgresSerZoneRepository(pg_engine)

    repo.bulk_replace([_make_zone_record(spot_count=-1)])

    zones = repo.list_all()

    assert len(zones) == 1
    assert zones[0].spot_count == -1


def test_list_all_returns_empty_when_table_is_empty(pg_engine) -> None:
    """list_all returns an empty list when no zones are stored."""
    repo = PostgresSerZoneRepository(pg_engine)
    repo.bulk_replace([])

    result = repo.list_all()

    assert result == []


def test_list_all_returns_all_inserted_zones(pg_engine) -> None:
    """list_all returns all zones after bulk_replace."""
    repo = PostgresSerZoneRepository(pg_engine)

    repo.bulk_replace(
        [
            _make_zone_record(zone_number="100", zone_type="Azul", geometry_wkt=_SQUARE_A_WKT),
            _make_zone_record(zone_number="200", zone_type="Verde", geometry_wkt=_SQUARE_B_WKT),
        ]
    )

    result = repo.list_all()

    assert len(result) == 2
    zone_numbers = {z.zone_number for z in result}
    assert zone_numbers == {"100", "200"}


def test_list_all_does_not_query_ser_zone_streets(pg_engine) -> None:
    """list_all must not populate/require street names — see design.md D9."""
    repo = PostgresSerZoneRepository(pg_engine)
    repo.bulk_replace([_make_zone_record(street_names=["ABADA", "GRAN VIA"])])

    zones = repo.list_all()

    assert len(zones) == 1
    assert not hasattr(zones[0], "street_names")


def test_get_street_names_returns_all_streets_for_zone(pg_engine) -> None:
    repo = PostgresSerZoneRepository(pg_engine)
    repo.bulk_replace([_make_zone_record(street_names=["ABADA", "GRAN VIA", "MAYOR"])])

    streets = repo.get_street_names("163", "Azul")

    assert set(streets) == {"ABADA", "GRAN VIA", "MAYOR"}


def test_get_street_names_returns_empty_for_unknown_zone(pg_engine) -> None:
    repo = PostgresSerZoneRepository(pg_engine)
    repo.bulk_replace([])

    streets = repo.get_street_names("999", "Azul")

    assert streets == []


def test_old_point_columns_are_absent(pg_engine) -> None:
    """latitude/longitude/utm_x/utm_y must not be present in the schema."""
    with pg_engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'ser_zones'
                """
            )
        )
        columns = {row[0] for row in result}

    assert "latitude" not in columns, "latitude column must be dropped"
    assert "longitude" not in columns, "longitude column must be dropped"
    assert "utm_x" not in columns, "utm_x column must be dropped"
    assert "utm_y" not in columns, "utm_y column must be dropped"
    assert "street_name" not in columns, "street_name column must be dropped from ser_zones"
