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
    # Ensure table exists
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
                    longitude   DOUBLE PRECISION NOT NULL
                )
                """
            )
        )
        conn.execute(text("TRUNCATE ser_zones"))
    yield engine
    # Cleanup
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE ser_zones"))
    engine.dispose()


def test_bulk_replace_and_find_nearest(pg_engine) -> None:
    """Insert a record via bulk_replace, then find it via find_nearest."""
    repo = PostgresSerZoneRepository(pg_engine)

    records = [
        {
            "street_name": "Calle Mayor",
            "zone_code": "SER-A",
            "zone_label": "Blue",
            "latitude": 40.4168,
            "longitude": -3.7038,
        }
    ]
    inserted = repo.bulk_replace(records)
    assert inserted == 1

    location = GeoLocation(lat=40.4168, lng=-3.7038)
    zone = repo.find_nearest(location)

    assert zone is not None
    assert zone.street_name == "Calle Mayor"
    assert zone.zone_code == "SER-A"
    assert zone.zone_label == "Blue"
    assert abs(zone.location.lat - 40.4168) < 0.001
    assert abs(zone.location.lng - (-3.7038)) < 0.001


def test_find_nearest_returns_none_when_empty(pg_engine) -> None:
    """find_nearest returns None when the table is empty."""
    repo = PostgresSerZoneRepository(pg_engine)
    repo.bulk_replace([])  # Ensures table is truncated

    location = GeoLocation(lat=40.4168, lng=-3.7038)
    zone = repo.find_nearest(location)

    assert zone is None


def test_bulk_replace_truncates_old_records(pg_engine) -> None:
    """bulk_replace removes existing data before inserting new records."""
    repo = PostgresSerZoneRepository(pg_engine)

    first_batch = [
        {
            "street_name": "Old Street",
            "zone_code": "SER-V",
            "zone_label": "Green",
            "latitude": 40.4000,
            "longitude": -3.7000,
        }
    ]
    repo.bulk_replace(first_batch)

    second_batch = [
        {
            "street_name": "New Street",
            "zone_code": "SER-A",
            "zone_label": "Blue",
            "latitude": 40.4168,
            "longitude": -3.7038,
        }
    ]
    repo.bulk_replace(second_batch)

    location = GeoLocation(lat=40.4000, lng=-3.7000)
    zone = repo.find_nearest(location, radius_deg=0.1)

    # Should find the New Street record, not Old Street
    assert zone is not None
    assert zone.street_name == "New Street"
