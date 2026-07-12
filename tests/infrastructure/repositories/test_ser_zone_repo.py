"""
Unit tests for PostgresSerZoneRepository.list_all() row-level error isolation.

Uses a mocked SQLAlchemy Engine/Connection so this runs with no real
PostgreSQL instance (unlike test_ser_zone_repo_integration.py, which is
skipped without POSTGRES_DSN). Only list_all()'s per-row try/except is
covered here — full round-trip behaviour is covered by the integration test.
"""

from unittest.mock import MagicMock

from mobility_manager.infrastructure.repositories.postgres.ser_zone_repo import (
    PostgresSerZoneRepository,
)

_VALID_WKT = "POLYGON((440584 4474459, 440604 4474459, 440604 4474479, 440584 4474479, 440584 4474459))"


def _make_engine_with_rows(rows: list[tuple]) -> MagicMock:
    """Build a mocked Engine whose connect().execute().fetchall() returns rows."""
    engine = MagicMock()
    conn = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    conn.execute.return_value.fetchall.return_value = rows
    return engine


def test_list_all_skips_row_with_invalid_geometry_and_keeps_valid_rows() -> None:
    rows = [
        ("100", "Azul", "CENTRO", 5, _VALID_WKT),
        ("200", "Verde", "CENTRO", 3, "NOT VALID WKT"),
        ("300", "Rojo", "CENTRO", 7, _VALID_WKT),
    ]
    engine = _make_engine_with_rows(rows)
    repo = PostgresSerZoneRepository(engine)

    zones = repo.list_all()

    zone_numbers = {z.zone_number for z in zones}
    assert zone_numbers == {"100", "300"}
    assert len(zones) == 2


def test_list_all_returns_empty_list_when_all_rows_invalid() -> None:
    rows = [
        ("100", "Azul", "CENTRO", 5, "garbage"),
        ("200", "Verde", "CENTRO", 3, "also garbage"),
    ]
    engine = _make_engine_with_rows(rows)
    repo = PostgresSerZoneRepository(engine)

    zones = repo.list_all()

    assert zones == []


def test_list_all_returns_all_rows_when_all_valid() -> None:
    rows = [
        ("100", "Azul", "CENTRO", 5, _VALID_WKT),
        ("200", "Verde", "CENTRO", 3, _VALID_WKT),
    ]
    engine = _make_engine_with_rows(rows)
    repo = PostgresSerZoneRepository(engine)

    zones = repo.list_all()

    assert len(zones) == 2


# ---------------------------------------------------------------------------
# get_zone_area / list_zone_areas
# ---------------------------------------------------------------------------


def _make_engine_with_fetchone(row: tuple | None) -> MagicMock:
    engine = MagicMock()
    conn = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    conn.execute.return_value.fetchone.return_value = row
    return engine


def test_get_zone_area_returns_zone_area_for_known_zone_number() -> None:
    engine = _make_engine_with_fetchone(("163", "Sol", _VALID_WKT))
    repo = PostgresSerZoneRepository(engine)

    zone_area = repo.get_zone_area("163")

    assert zone_area is not None
    assert zone_area.zone_number == "163"
    assert zone_area.neighbourhood == "Sol"
    assert zone_area.geometry.is_valid


def test_get_zone_area_returns_none_for_unknown_zone_number() -> None:
    engine = _make_engine_with_fetchone(None)
    repo = PostgresSerZoneRepository(engine)

    assert repo.get_zone_area("999") is None


def test_get_zone_area_returns_none_for_invalid_geometry() -> None:
    engine = _make_engine_with_fetchone(("163", "Sol", "NOT VALID WKT"))
    repo = PostgresSerZoneRepository(engine)

    assert repo.get_zone_area("163") is None


def test_list_zone_areas_returns_all_rows() -> None:
    rows = [
        ("100", "Palacio", _VALID_WKT),
        ("200", "Sol", _VALID_WKT),
    ]
    engine = _make_engine_with_rows(rows)
    repo = PostgresSerZoneRepository(engine)

    zone_areas = repo.list_zone_areas()

    assert len(zone_areas) == 2
    assert {za.zone_number for za in zone_areas} == {"100", "200"}


def test_list_zone_areas_skips_invalid_geometry_row() -> None:
    rows = [
        ("100", "Palacio", _VALID_WKT),
        ("200", "Sol", "garbage"),
    ]
    engine = _make_engine_with_rows(rows)
    repo = PostgresSerZoneRepository(engine)

    zone_areas = repo.list_zone_areas()

    assert len(zone_areas) == 1
    assert zone_areas[0].zone_number == "100"
