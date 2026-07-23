"""
Integration tests for PostgresElParkingZoneMappingRepository.

Requires POSTGRES_DSN environment variable. Skipped automatically if absent,
mirroring test_user_ser_provider_config_repo_integration.py's pattern.
"""

import os
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text


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
                CREATE TABLE IF NOT EXISTS ser_ticket_provider_zone_mappings (
                    city_code TEXT NOT NULL REFERENCES cities(code),
                    provider TEXT NOT NULL,
                    id_ser_town TEXT NOT NULL,
                    zones_payload JSONB NOT NULL,
                    fetched_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (city_code, provider)
                )
                """
            )
        )
        conn.execute(text("TRUNCATE ser_ticket_provider_zone_mappings CASCADE"))
        conn.execute(
            text("INSERT INTO cities (code, name) VALUES ('madrid', 'Madrid') ON CONFLICT (code) DO NOTHING")
        )
    yield engine
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE ser_ticket_provider_zone_mappings CASCADE"))
    engine.dispose()


def _make_mapping():
    from mobility_manager.infrastructure.ser_ticket_providers.elparking.zone_mapping import (
        ElParkingRate,
        ElParkingZone,
        ElParkingZoneMapping,
    )

    return ElParkingZoneMapping(
        id_ser_town="town-1",
        zones=[
            ElParkingZone(
                id="zone-84",
                name="84 - PILAR",
                polygon_wkt="POLYGON((-3.70 40.40, -3.699 40.40, -3.699 40.401, -3.70 40.401, -3.70 40.40))",
                rates=[ElParkingRate(id="rate-azul", name="Tarifa Azul")],
            )
        ],
        fetched_at=datetime.now(UTC),
    )


def test_save_then_get_round_trips_mapping(pg_engine) -> None:
    from mobility_manager.infrastructure.ser_ticket_providers.elparking.zone_mapping_repository import (
        PostgresElParkingZoneMappingRepository,
    )

    repo = PostgresElParkingZoneMappingRepository(pg_engine)
    mapping = _make_mapping()

    repo.save("madrid", "elparking", mapping)
    recovered = repo.get("madrid", "elparking")

    assert recovered is not None
    assert recovered.id_ser_town == "town-1"
    assert len(recovered.zones) == 1
    assert recovered.zones[0].id == "zone-84"
    assert recovered.zones[0].name == "84 - PILAR"
    assert recovered.zones[0].polygon_wkt == mapping.zones[0].polygon_wkt
    assert recovered.zones[0].rates[0].id == "rate-azul"
    assert recovered.zones[0].rates[0].name == "Tarifa Azul"


def test_get_returns_none_when_absent(pg_engine) -> None:
    from mobility_manager.infrastructure.ser_ticket_providers.elparking.zone_mapping_repository import (
        PostgresElParkingZoneMappingRepository,
    )

    repo = PostgresElParkingZoneMappingRepository(pg_engine)

    assert repo.get("madrid", "elparking") is None


def test_upsert_overwrites_existing_row_for_same_pair(pg_engine) -> None:
    from mobility_manager.infrastructure.ser_ticket_providers.elparking.zone_mapping import (
        ElParkingZoneMapping,
    )
    from mobility_manager.infrastructure.ser_ticket_providers.elparking.zone_mapping_repository import (
        PostgresElParkingZoneMappingRepository,
    )

    repo = PostgresElParkingZoneMappingRepository(pg_engine)
    first = _make_mapping()
    repo.save("madrid", "elparking", first)

    second = ElParkingZoneMapping(id_ser_town="town-2", zones=[], fetched_at=datetime.now(UTC))
    repo.save("madrid", "elparking", second)

    with pg_engine.connect() as conn:
        count = conn.execute(
            text(
                "SELECT COUNT(*) FROM ser_ticket_provider_zone_mappings "
                "WHERE city_code = 'madrid' AND provider = 'elparking'"
            )
        ).scalar()
    assert count == 1

    recovered = repo.get("madrid", "elparking")
    assert recovered is not None
    assert recovered.id_ser_town == "town-2"
    assert recovered.zones == []


def test_get_returns_none_when_fetched_at_is_30_or_more_days_old(pg_engine) -> None:
    from mobility_manager.infrastructure.ser_ticket_providers.elparking.zone_mapping_repository import (
        PostgresElParkingZoneMappingRepository,
    )

    repo = PostgresElParkingZoneMappingRepository(pg_engine)
    repo.save("madrid", "elparking", _make_mapping())

    stale_fetched_at = datetime.now(UTC) - timedelta(days=30)
    with pg_engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE ser_ticket_provider_zone_mappings SET fetched_at = :fetched_at "
                "WHERE city_code = 'madrid' AND provider = 'elparking'"
            ),
            {"fetched_at": stale_fetched_at},
        )

    assert repo.get("madrid", "elparking") is None


def test_get_returns_none_for_malformed_zones_payload(pg_engine) -> None:
    """A structurally malformed cache row (missing an expected zone key) is treated as a cache miss."""
    from mobility_manager.infrastructure.ser_ticket_providers.elparking.zone_mapping_repository import (
        PostgresElParkingZoneMappingRepository,
    )

    repo = PostgresElParkingZoneMappingRepository(pg_engine)

    with pg_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO ser_ticket_provider_zone_mappings
                    (city_code, provider, id_ser_town, zones_payload, fetched_at)
                VALUES
                    (:city_code, :provider, :id_ser_town, CAST(:zones_payload AS JSONB), :fetched_at)
                """
            ),
            {
                "city_code": "madrid",
                "provider": "elparking",
                "id_ser_town": "town-1",
                # Missing "polygon_wkt" — structurally malformed.
                "zones_payload": '[{"id": "zone-84", "name": "84 - PILAR", "rates": []}]',
                "fetched_at": datetime.now(UTC),
            },
        )

    assert repo.get("madrid", "elparking") is None


def test_get_returns_mapping_when_fetched_at_is_just_under_30_days_old(pg_engine) -> None:
    from mobility_manager.infrastructure.ser_ticket_providers.elparking.zone_mapping_repository import (
        PostgresElParkingZoneMappingRepository,
    )

    repo = PostgresElParkingZoneMappingRepository(pg_engine)
    repo.save("madrid", "elparking", _make_mapping())

    fresh_fetched_at = datetime.now(UTC) - timedelta(days=29, hours=23)
    with pg_engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE ser_ticket_provider_zone_mappings SET fetched_at = :fetched_at "
                "WHERE city_code = 'madrid' AND provider = 'elparking'"
            ),
            {"fetched_at": fresh_fetched_at},
        )

    assert repo.get("madrid", "elparking") is not None
