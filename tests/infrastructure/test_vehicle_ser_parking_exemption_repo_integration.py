"""
Integration tests for PostgresVehicleSerParkingExemptionRepository.

Requires POSTGRES_DSN environment variable. Skipped automatically if absent,
mirroring tests/infrastructure/test_vehicle_ambient_label_repo_integration.py.
"""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from mobility_manager.domain.exceptions import InvalidSerParkingExemptionZoneError
from mobility_manager.infrastructure.repositories.postgres.vehicle_ser_parking_exemption_repo import (
    PostgresVehicleSerParkingExemptionRepository,
)


@pytest.fixture()
def pg_engine():
    dsn = os.environ.get("POSTGRES_DSN")
    if not dsn:
        pytest.skip("POSTGRES_DSN not set — skipping integration test")
    engine = create_engine(dsn, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY,
                    google_sub TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS vehicles (
                    id UUID PRIMARY KEY,
                    brand VARCHAR(20) NOT NULL,
                    display_name VARCHAR(255) NOT NULL,
                    vin VARCHAR(50),
                    license_plate VARCHAR(20),
                    created_at TIMESTAMPTZ NOT NULL,
                    user_id UUID NOT NULL REFERENCES users(id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS cities (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS ser_zone_areas (
                    city_code TEXT NOT NULL REFERENCES cities(code),
                    zone_number VARCHAR(10) NOT NULL,
                    neighbourhood TEXT NOT NULL,
                    geometry_wkt TEXT NOT NULL,
                    PRIMARY KEY (city_code, zone_number)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS vehicle_ser_parking_exemptions (
                    vehicle_id UUID PRIMARY KEY REFERENCES vehicles(id) ON DELETE CASCADE,
                    city_code TEXT NOT NULL,
                    zone_number VARCHAR(10) NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    CONSTRAINT fk_vehicle_ser_parking_exemptions_zone_area
                        FOREIGN KEY (city_code, zone_number) REFERENCES ser_zone_areas(city_code, zone_number)
                )
                """
            )
        )
        conn.execute(
            text(
                "TRUNCATE vehicle_ser_parking_exemptions, ser_zone_areas, vehicles, users, cities CASCADE"
            )
        )
        conn.execute(
            text("INSERT INTO cities (code, name) VALUES ('madrid', 'Madrid') ON CONFLICT DO NOTHING")
        )
        conn.execute(
            text(
                "INSERT INTO ser_zone_areas (city_code, zone_number, neighbourhood, geometry_wkt) "
                "VALUES ('madrid', '163', 'Sol', 'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))')"
            )
        )
    yield engine
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE vehicle_ser_parking_exemptions, ser_zone_areas, vehicles, users, cities CASCADE"
            )
        )
    engine.dispose()


def _insert_vehicle(engine, vehicle_id) -> None:
    user_id = uuid4()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, display_name, created_at)"
                " VALUES (:id, :sub, 'test@example.com', 'Test User', :now)"
            ),
            {"id": str(user_id), "sub": str(uuid4()), "now": datetime.now(UTC)},
        )
        conn.execute(
            text(
                "INSERT INTO vehicles (id, brand, display_name, license_plate, created_at, user_id)"
                " VALUES (:id, 'generic', 'Test', '1234ABC', :now, :user_id)"
            ),
            {"id": str(vehicle_id), "now": datetime.now(UTC), "user_id": str(user_id)},
        )


def test_find_by_vehicle_id_returns_none_when_unset(pg_engine) -> None:
    repo = PostgresVehicleSerParkingExemptionRepository(pg_engine)
    assert repo.find_by_vehicle_id(uuid4()) is None


def test_upsert_creates_a_row(pg_engine) -> None:
    repo = PostgresVehicleSerParkingExemptionRepository(pg_engine)
    vehicle_id = uuid4()
    _insert_vehicle(pg_engine, vehicle_id)

    result = repo.upsert(vehicle_id, "madrid", "163")

    assert result.vehicle_id == vehicle_id
    assert result.city_code == "madrid"
    assert result.zone_number == "163"

    fetched = repo.find_by_vehicle_id(vehicle_id)
    assert fetched is not None
    assert fetched.city_code == "madrid"
    assert fetched.zone_number == "163"


def test_upsert_replaces_existing_row_not_duplicates(pg_engine) -> None:
    repo = PostgresVehicleSerParkingExemptionRepository(pg_engine)
    vehicle_id = uuid4()
    _insert_vehicle(pg_engine, vehicle_id)
    with pg_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO ser_zone_areas (city_code, zone_number, neighbourhood, geometry_wkt) "
                "VALUES ('madrid', '200', 'Malasaña', 'POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))')"
            )
        )

    repo.upsert(vehicle_id, "madrid", "163")
    repo.upsert(vehicle_id, "madrid", "200")

    fetched = repo.find_by_vehicle_id(vehicle_id)
    assert fetched is not None
    assert fetched.zone_number == "200"

    with pg_engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM vehicle_ser_parking_exemptions WHERE vehicle_id = :id"),
            {"id": str(vehicle_id)},
        ).scalar_one()
    assert count == 1


def test_upsert_with_unknown_zone_raises_invalid_zone_error(pg_engine) -> None:
    repo = PostgresVehicleSerParkingExemptionRepository(pg_engine)
    vehicle_id = uuid4()
    _insert_vehicle(pg_engine, vehicle_id)

    with pytest.raises(InvalidSerParkingExemptionZoneError):
        repo.upsert(vehicle_id, "madrid", "999999")


def test_upsert_with_nonexistent_vehicle_does_not_raise_invalid_zone_error(pg_engine) -> None:
    """
    A vehicle_id FK violation (no matching vehicles row) must not be
    mislabeled as InvalidSerParkingExemptionZoneError — that error is
    reserved for the (city_code, zone_number) FK specifically, discriminated
    by constraint name. See vehicle_ser_parking_exemption_repo.py's
    _ZONE_AREA_FK_CONSTRAINT.
    """
    repo = PostgresVehicleSerParkingExemptionRepository(pg_engine)
    nonexistent_vehicle_id = uuid4()  # deliberately never inserted into vehicles

    # InvalidSerParkingExemptionZoneError is not an IntegrityError subclass,
    # so this also proves the domain error was not (mis)raised here.
    with pytest.raises(IntegrityError):
        repo.upsert(nonexistent_vehicle_id, "madrid", "163")


def test_delete_removes_existing_row(pg_engine) -> None:
    repo = PostgresVehicleSerParkingExemptionRepository(pg_engine)
    vehicle_id = uuid4()
    _insert_vehicle(pg_engine, vehicle_id)
    repo.upsert(vehicle_id, "madrid", "163")

    repo.delete(vehicle_id)

    assert repo.find_by_vehicle_id(vehicle_id) is None


def test_delete_is_idempotent_when_no_row_exists(pg_engine) -> None:
    repo = PostgresVehicleSerParkingExemptionRepository(pg_engine)
    vehicle_id = uuid4()
    _insert_vehicle(pg_engine, vehicle_id)

    repo.delete(vehicle_id)  # must not raise


def test_deleting_vehicle_cascades_to_exemption_row(pg_engine) -> None:
    repo = PostgresVehicleSerParkingExemptionRepository(pg_engine)
    vehicle_id = uuid4()
    _insert_vehicle(pg_engine, vehicle_id)
    repo.upsert(vehicle_id, "madrid", "163")

    with pg_engine.begin() as conn:
        conn.execute(text("DELETE FROM vehicles WHERE id = :id"), {"id": str(vehicle_id)})

    assert repo.find_by_vehicle_id(vehicle_id) is None
