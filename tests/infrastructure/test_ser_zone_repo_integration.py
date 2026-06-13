"""
Integration tests for PostgresSerZoneRepository.

These tests require a running PostgreSQL instance.
Set POSTGRES_DSN env var or skip tests if not available.
"""
import os

import pytest
from sqlalchemy import create_engine, text

from mobility_manager.domain.value_objects.location import GeoLocation
from mobility_manager.infrastructure.repositories.postgres.ser_zone_repo import (
    PostgresSerZoneRepository,
    ser_zones_table,
)


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
                    id          SERIAL PRIMARY KEY,
                    street_name TEXT NOT NULL,
                    zone_code   TEXT NOT NULL,
                    zone_label  TEXT NOT NULL,
                    latitude    DOUBLE PRECISION NOT NULL,
                    longitude   DOUBLE PRECISION NOT NULL,
                    utm_x       DOUBLE PRECISION NOT NULL,
                    utm_y       DOUBLE PRECISION NOT NULL
                )
                """
            )
        )
        conn.execute(text("TRUNCATE ser_zones"))
    yield engine
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE ser_zones"))
    engine.dispose()


def test_bulk_replace_and_find_nearest(pg_engine) -> None:
    """Insert a record via bulk_replace, then find it via find_nearest."""
    repo = PostgresSerZoneRepository(pg_engine)

    records = [
        {
            "street_name": "Calle Mayor",
            "zone_code": "011",
            "zone_label": "011",
            "latitude": 40.4168,
            "longitude": -3.7038,
            "utm_x": 440594.0,   # EPSG:25830 easting near Puerta del Sol
            "utm_y": 4474469.0,  # EPSG:25830 northing near Puerta del Sol
        }
    ]
    inserted = repo.bulk_replace(records)
    assert inserted == 1

    location = GeoLocation(lat=40.4168, lng=-3.7038)
    zone = repo.find_nearest(location)

    assert zone is not None
    assert zone.street_name == "Calle Mayor"
    assert zone.zone_code == "011"
    assert zone.zone_label == "011"
    assert abs(zone.location.lat - 40.4168) < 0.001
    assert abs(zone.location.lng - (-3.7038)) < 0.001


def test_find_nearest_returns_none_when_empty(pg_engine) -> None:
    """find_nearest returns None when the table is empty."""
    repo = PostgresSerZoneRepository(pg_engine)
    repo.bulk_replace([])

    location = GeoLocation(lat=40.4168, lng=-3.7038)
    zone = repo.find_nearest(location)

    assert zone is None


def test_bulk_replace_truncates_old_records(pg_engine) -> None:
    """bulk_replace removes existing data before inserting new records."""
    repo = PostgresSerZoneRepository(pg_engine)

    first_batch = [
        {
            "street_name": "Old Street",
            "zone_code": "021",
            "zone_label": "021",
            "latitude": 40.4000,
            "longitude": -3.7000,
            "utm_x": 441203.0,
            "utm_y": 4472691.0,
        }
    ]
    repo.bulk_replace(first_batch)

    second_batch = [
        {
            "street_name": "New Street",
            "zone_code": "011",
            "zone_label": "011",
            "latitude": 40.4168,
            "longitude": -3.7038,
            "utm_x": 440594.0,
            "utm_y": 4474469.0,
        }
    ]
    repo.bulk_replace(second_batch)

    location = GeoLocation(lat=40.4000, lng=-3.7000)
    zone = repo.find_nearest(location, radius_deg=0.1)

    # Only New Street remains after the second bulk_replace.
    assert zone is not None
    assert zone.street_name == "New Street"
