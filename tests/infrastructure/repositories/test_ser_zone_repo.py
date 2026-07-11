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
