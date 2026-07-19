"""
Integration tests for PostgresSerZoneRepository.

These tests require a running PostgreSQL instance.
Set POSTGRES_DSN env var or skip tests if not available.
"""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from shapely.geometry import Polygon
from sqlalchemy import create_engine, text

from mobility_manager.domain.value_objects.location import GeoLocation
from mobility_manager.infrastructure.repositories.postgres.ser_zone_repo import (
    PostgresSerZoneRepository,
)
from mobility_manager.infrastructure.repositories.postgres.vehicle_ser_parking_exemption_repo import (
    PostgresVehicleSerParkingExemptionRepository,
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
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS ser_zone_areas (
                    zone_number    VARCHAR(10) PRIMARY KEY,
                    neighbourhood  TEXT NOT NULL,
                    geometry_wkt   TEXT NOT NULL
                )
                """
            )
        )
        conn.execute(text("TRUNCATE ser_zones"))
        conn.execute(text("TRUNCATE ser_zone_streets"))
        conn.execute(text("TRUNCATE ser_zone_areas"))
    yield engine
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE ser_zones"))
        conn.execute(text("TRUNCATE ser_zone_streets"))
        conn.execute(text("TRUNCATE ser_zone_areas"))
    engine.dispose()


def _make_zone_record(
    zone_number: str = "163",
    zone_type: str = "Azul",
    district: str = "CENTRO",
    spot_count: int = 15,
    geometry_wkt: str = _SQUARE_A_WKT,
    street_names: list[str] | None = None,
    city_code: str = "madrid",
) -> dict:
    return {
        "city_code": city_code,
        "zone_number": zone_number,
        "zone_type": zone_type,
        "district": district,
        "spot_count": spot_count,
        "geometry_wkt": geometry_wkt,
        "street_names": street_names if street_names is not None else ["ABADA"],
    }


def _make_zone_area_record(
    zone_number: str = "163",
    neighbourhood: str = "Sol",
    geometry_wkt: str = _SQUARE_A_WKT,
    city_code: str = "madrid",
) -> dict:
    return {
        "city_code": city_code,
        "zone_number": zone_number,
        "neighbourhood": neighbourhood,
        "geometry_wkt": geometry_wkt,
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

    streets = repo.get_street_names("madrid", "163", "Azul")

    assert set(streets) == {"ABADA", "GRAN VIA", "MAYOR"}


def test_get_street_names_returns_empty_for_unknown_zone(pg_engine) -> None:
    repo = PostgresSerZoneRepository(pg_engine)
    repo.bulk_replace([])

    streets = repo.get_street_names("madrid", "999", "Azul")

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


# ---------------------------------------------------------------------------
# ser_zone_areas: get_zone_area / list_zone_areas / bulk_replace
# ---------------------------------------------------------------------------


def test_bulk_replace_persists_zone_areas(pg_engine) -> None:
    repo = PostgresSerZoneRepository(pg_engine)

    inserted = repo.bulk_replace(
        [_make_zone_record()],
        zone_areas=[_make_zone_area_record()],
    )

    assert inserted == 1
    zone_area = repo.get_zone_area("madrid", "163")
    assert zone_area is not None
    assert zone_area.neighbourhood == "Sol"


def test_get_zone_area_returns_none_for_unknown_zone_number(pg_engine) -> None:
    repo = PostgresSerZoneRepository(pg_engine)
    repo.bulk_replace([_make_zone_record()], zone_areas=[_make_zone_area_record()])

    assert repo.get_zone_area("madrid", "999") is None


def test_list_zone_areas_returns_all_rows(pg_engine) -> None:
    repo = PostgresSerZoneRepository(pg_engine)
    repo.bulk_replace(
        [
            _make_zone_record(zone_number="100", zone_type="Azul", geometry_wkt=_SQUARE_A_WKT),
            _make_zone_record(zone_number="200", zone_type="Verde", geometry_wkt=_SQUARE_B_WKT),
        ],
        zone_areas=[
            _make_zone_area_record(zone_number="100", neighbourhood="Palacio", geometry_wkt=_SQUARE_A_WKT),
            _make_zone_area_record(zone_number="200", neighbourhood="Sol", geometry_wkt=_SQUARE_B_WKT),
        ],
    )

    zone_areas = repo.list_zone_areas()

    assert len(zone_areas) == 2
    assert {za.zone_number for za in zone_areas} == {"100", "200"}


def test_bulk_replace_truncates_old_zone_areas(pg_engine) -> None:
    repo = PostgresSerZoneRepository(pg_engine)
    repo.bulk_replace(
        [_make_zone_record(zone_number="100", geometry_wkt=_SQUARE_A_WKT)],
        zone_areas=[_make_zone_area_record(zone_number="100", geometry_wkt=_SQUARE_A_WKT)],
    )
    repo.bulk_replace(
        [_make_zone_record(zone_number="200", geometry_wkt=_SQUARE_B_WKT)],
        zone_areas=[_make_zone_area_record(zone_number="200", geometry_wkt=_SQUARE_B_WKT)],
    )

    zone_areas = repo.list_zone_areas()

    assert len(zone_areas) == 1
    assert zone_areas[0].zone_number == "200"


def test_list_all_find_nearest_find_containing_never_query_ser_zone_areas(pg_engine) -> None:
    """
    list_all()/find_nearest()/find_containing() must never depend on
    ser_zone_areas — frontier data is fetched only via its own explicit
    method call (design.md D6 of add-ser-zone-frontiers).
    """
    repo = PostgresSerZoneRepository(pg_engine)
    repo.bulk_replace([_make_zone_record()], zone_areas=[])

    zones = repo.list_all()
    assert len(zones) == 1
    assert not hasattr(zones[0], "neighbourhood")

    from pyproj import Transformer

    square = Polygon([(440584, 4474459), (440604, 4474459), (440604, 4474479), (440584, 4474479)])
    centroid = square.centroid
    utm_to_wgs84 = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)
    lng, lat = utm_to_wgs84.transform(centroid.x, centroid.y)

    containing = repo.find_containing(GeoLocation(lat=lat, lng=lng))
    assert containing is not None

    nearest = repo.find_nearest(GeoLocation(lat=lat, lng=lng))
    assert nearest is not None


def test_bulk_replace_with_no_zone_areas_argument_still_works(pg_engine) -> None:
    """bulk_replace's zone_areas argument is optional and defaults sanely."""
    repo = PostgresSerZoneRepository(pg_engine)
    inserted = repo.bulk_replace([_make_zone_record()])

    assert inserted == 1
    assert repo.list_zone_areas() == []


def test_ingesting_one_city_does_not_affect_another_citys_stored_data(pg_engine) -> None:
    """
    Ingesting Barcelona's SER zones via bulk_replace() must leave Madrid's
    previously stored zone, street, and frontier rows fully intact and
    queryable — proven against real stored rows in a live database.

    tests/infrastructure/repositories/test_ser_zone_repo.py only proves the
    equivalent claim at the mocked SQL-string level (asserting the DELETE
    statements are parameterized to the ingested city); this test closes the
    gap by asserting on data actually round-tripped through Postgres.
    """
    with pg_engine.begin() as conn:
        conn.execute(
            text("INSERT INTO cities (code, name) VALUES ('barcelona', 'Barcelona') ON CONFLICT (code) DO NOTHING")
        )

    repo = PostgresSerZoneRepository(pg_engine)

    repo.bulk_replace(
        [
            _make_zone_record(
                city_code="madrid",
                zone_number="163",
                zone_type="Azul",
                geometry_wkt=_SQUARE_A_WKT,
                street_names=["ABADA"],
            )
        ],
        zone_areas=[
            _make_zone_area_record(
                city_code="madrid", zone_number="163", neighbourhood="Sol", geometry_wkt=_SQUARE_A_WKT
            )
        ],
    )

    # Ingesting Barcelona's own zone must not touch Madrid's rows above.
    repo.bulk_replace(
        [
            _make_zone_record(
                city_code="barcelona",
                zone_number="200",
                zone_type="Verde",
                geometry_wkt=_SQUARE_B_WKT,
                street_names=["DIAGONAL"],
            )
        ],
        zone_areas=[
            _make_zone_area_record(
                city_code="barcelona", zone_number="200", neighbourhood="Eixample", geometry_wkt=_SQUARE_B_WKT
            )
        ],
    )

    zones_by_city = {z.city_code: z for z in repo.list_all()}
    assert set(zones_by_city) == {"madrid", "barcelona"}
    assert zones_by_city["madrid"].zone_number == "163"
    assert zones_by_city["barcelona"].zone_number == "200"

    assert repo.get_street_names("madrid", "163", "Azul") == ["ABADA"]

    madrid_area = repo.get_zone_area("madrid", "163")
    assert madrid_area is not None
    assert madrid_area.neighbourhood == "Sol"


# ---------------------------------------------------------------------------
# list_zones_for_city / list_zone_areas_for_city — city-scoped queries
# (add-vehicle-ser-parking-exemption design.md D7)
# ---------------------------------------------------------------------------


def test_list_zones_for_city_excludes_other_citys_rows(pg_engine) -> None:
    """
    list_zones_for_city must exclude another city's zones — proving the
    latent gap in list_all() (unfiltered by city_code) is closed for the
    new scoped method.
    """
    with pg_engine.begin() as conn:
        conn.execute(
            text("INSERT INTO cities (code, name) VALUES ('barcelona', 'Barcelona') ON CONFLICT (code) DO NOTHING")
        )

    repo = PostgresSerZoneRepository(pg_engine)
    repo.bulk_replace(
        [_make_zone_record(city_code="madrid", zone_number="163", zone_type="Azul", geometry_wkt=_SQUARE_A_WKT)]
    )
    repo.bulk_replace(
        [_make_zone_record(city_code="barcelona", zone_number="200", zone_type="Verde", geometry_wkt=_SQUARE_B_WKT)]
    )

    madrid_zones = repo.list_zones_for_city("madrid")

    assert len(madrid_zones) == 1
    assert madrid_zones[0].zone_number == "163"
    assert all(z.city_code == "madrid" for z in madrid_zones)


def test_list_zone_areas_for_city_excludes_other_citys_rows(pg_engine) -> None:
    """list_zone_areas_for_city must exclude another city's frontiers."""
    with pg_engine.begin() as conn:
        conn.execute(
            text("INSERT INTO cities (code, name) VALUES ('barcelona', 'Barcelona') ON CONFLICT (code) DO NOTHING")
        )

    repo = PostgresSerZoneRepository(pg_engine)
    repo.bulk_replace(
        [_make_zone_record(city_code="madrid", zone_number="163", geometry_wkt=_SQUARE_A_WKT)],
        zone_areas=[
            _make_zone_area_record(
                city_code="madrid", zone_number="163", neighbourhood="Sol", geometry_wkt=_SQUARE_A_WKT
            )
        ],
    )
    repo.bulk_replace(
        [_make_zone_record(city_code="barcelona", zone_number="200", geometry_wkt=_SQUARE_B_WKT)],
        zone_areas=[
            _make_zone_area_record(
                city_code="barcelona", zone_number="200", neighbourhood="Eixample", geometry_wkt=_SQUARE_B_WKT
            )
        ],
    )

    madrid_areas = repo.list_zone_areas_for_city("madrid")

    assert len(madrid_areas) == 1
    assert madrid_areas[0].zone_number == "163"
    assert madrid_areas[0].neighbourhood == "Sol"
    assert all(za.city_code == "madrid" for za in madrid_areas)


def test_list_zones_for_city_returns_empty_when_no_zones_for_that_city(pg_engine) -> None:
    repo = PostgresSerZoneRepository(pg_engine)
    repo.bulk_replace([_make_zone_record(city_code="madrid")])

    assert repo.list_zones_for_city("madrid") != []
    with pg_engine.begin() as conn:
        conn.execute(
            text("INSERT INTO cities (code, name) VALUES ('barcelona', 'Barcelona') ON CONFLICT (code) DO NOTHING")
        )
    assert repo.list_zones_for_city("barcelona") == []


# ---------------------------------------------------------------------------
# bulk_replace(): ser_zone_areas upsert-then-targeted-delete must not break
# vehicle_ser_parking_exemptions' composite FK (see
# add-vehicle-ser-parking-exemption tasks.md 11.4 — this is the live
# ForeignKeyViolation bug found from scheduled-ingestion Docker logs).
# ---------------------------------------------------------------------------


def _insert_vehicle_for_exemption_test(engine, vehicle_id) -> None:
    user_id = uuid4()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, display_name, created_at)"
                " VALUES (:id, :sub, 'exemption-test@example.com', 'Exemption Test User', :now)"
            ),
            {"id": str(user_id), "sub": str(uuid4()), "now": datetime.now(UTC)},
        )
        conn.execute(
            text(
                "INSERT INTO vehicles (id, brand, display_name, license_plate, created_at, user_id)"
                " VALUES (:id, 'generic', 'Exemption Test Vehicle', :plate, :now, :user_id)"
            ),
            {
                "id": str(vehicle_id),
                "plate": f"{str(vehicle_id)[:4].upper()}XYZ",
                "now": datetime.now(UTC),
                "user_id": str(user_id),
            },
        )


def _cleanup_vehicle_for_exemption_test(engine, vehicle_id) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM vehicle_ser_parking_exemptions WHERE vehicle_id = :id"), {"id": str(vehicle_id)})
        row = conn.execute(text("SELECT user_id FROM vehicles WHERE id = :id"), {"id": str(vehicle_id)}).fetchone()
        conn.execute(text("DELETE FROM vehicles WHERE id = :id"), {"id": str(vehicle_id)})
        if row is not None:
            conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": str(row[0])})


def test_bulk_replace_reingesting_same_zone_number_preserves_vehicle_exemption(pg_engine) -> None:
    """
    Re-ingesting a city whose fresh data still contains a zone_number that a
    vehicle is exempt for must succeed (not raise ForeignKeyViolation), must
    refresh that ser_zone_areas row's neighbourhood/geometry via upsert, and
    must leave the vehicle's exemption row completely untouched.
    """
    repo = PostgresSerZoneRepository(pg_engine)
    exemption_repo = PostgresVehicleSerParkingExemptionRepository(pg_engine)
    vehicle_id = uuid4()

    repo.bulk_replace(
        [_make_zone_record(zone_number="163")],
        zone_areas=[_make_zone_area_record(zone_number="163", neighbourhood="Sol")],
    )

    _insert_vehicle_for_exemption_test(pg_engine, vehicle_id)
    try:
        exemption_repo.upsert(vehicle_id, "madrid", "163")
        assert exemption_repo.find_by_vehicle_id(vehicle_id) is not None

        # Simulate a refreshed re-ingestion: same zone_number, different
        # neighbourhood/geometry (e.g. Barrios shapefile update).
        inserted = repo.bulk_replace(
            [_make_zone_record(zone_number="163", geometry_wkt=_SQUARE_B_WKT)],
            zone_areas=[
                _make_zone_area_record(zone_number="163", neighbourhood="Malasaña", geometry_wkt=_SQUARE_B_WKT)
            ],
        )
        assert inserted == 1

        zone_area = repo.get_zone_area("madrid", "163")
        assert zone_area is not None
        assert zone_area.neighbourhood == "Malasaña"

        fetched = exemption_repo.find_by_vehicle_id(vehicle_id)
        assert fetched is not None
        assert fetched.city_code == "madrid"
        assert fetched.zone_number == "163"
    finally:
        _cleanup_vehicle_for_exemption_test(pg_engine, vehicle_id)


def test_bulk_replace_retiring_zone_number_cascades_vehicle_exemption_deletion(pg_engine) -> None:
    """
    Re-ingesting a city whose fresh data no longer includes a zone_number
    that a vehicle is exempt for (the zone was retired) must succeed, must
    delete the now-stale ser_zone_areas row, and must cascade-delete the
    vehicle's now-meaningless exemption row.
    """
    repo = PostgresSerZoneRepository(pg_engine)
    exemption_repo = PostgresVehicleSerParkingExemptionRepository(pg_engine)
    vehicle_id = uuid4()

    repo.bulk_replace(
        [_make_zone_record(zone_number="163")],
        zone_areas=[_make_zone_area_record(zone_number="163", neighbourhood="Sol")],
    )

    _insert_vehicle_for_exemption_test(pg_engine, vehicle_id)
    try:
        exemption_repo.upsert(vehicle_id, "madrid", "163")
        assert exemption_repo.find_by_vehicle_id(vehicle_id) is not None

        # Fresh data no longer resolves zone_number "163" for madrid — it's retired.
        inserted = repo.bulk_replace(
            [_make_zone_record(zone_number="200", geometry_wkt=_SQUARE_B_WKT)],
            zone_areas=[
                _make_zone_area_record(zone_number="200", neighbourhood="Chamberí", geometry_wkt=_SQUARE_B_WKT)
            ],
        )
        assert inserted == 1

        assert repo.get_zone_area("madrid", "163") is None
        assert exemption_repo.find_by_vehicle_id(vehicle_id) is None
    finally:
        _cleanup_vehicle_for_exemption_test(pg_engine, vehicle_id)
