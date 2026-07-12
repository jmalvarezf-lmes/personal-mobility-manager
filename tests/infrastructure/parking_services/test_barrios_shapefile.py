"""
Unit tests for Madrid Barrios shapefile parsing.

Builds small synthetic in-memory .shp/.dbf fixtures via pyshp's Writer (no
network access, no real Madrid data needed) — shape_type=5 (Polygon), fields
COD_DISB (text) and NOMBRE (text), matching the real BARRIOS schema.
"""

import io
from unittest.mock import MagicMock, patch

import pytest
import shapefile

from mobility_manager.infrastructure.parking_services.madrid.barrios_shapefile import (
    fetch_barrios_zip,
    parse_barrios,
)

_SAMPLE_POLYGON = [(440000.0, 4474000.0), (440100.0, 4474000.0), (440100.0, 4474100.0), (440000.0, 4474100.0)]


def _build_shp_dbf(rows: list[tuple[str, str, list[tuple[float, float]]]]) -> tuple[io.BytesIO, io.BytesIO]:
    """Build in-memory .shp/.dbf streams for the given (cod_disb, nombre, points) rows."""
    shp = io.BytesIO()
    dbf = io.BytesIO()
    writer = shapefile.Writer(shp=shp, dbf=dbf, shapeType=shapefile.POLYGON)
    writer.field("COD_DISB", "C")
    writer.field("NOMBRE", "C")

    for cod_disb, nombre, points in rows:
        writer.poly([[[x, y] for x, y in points]])
        writer.record(cod_disb, nombre)

    writer.close()
    shp.seek(0)
    dbf.seek(0)
    return shp, dbf


def test_sample_rows_parse_expected_values() -> None:
    shp, dbf = _build_shp_dbf(
        [
            ("1-1", "Palacio", _SAMPLE_POLYGON),
            ("1-2", "Embajadores", _SAMPLE_POLYGON),
        ]
    )

    records = parse_barrios(shp, dbf)

    assert len(records) == 2
    assert records[0].cod_disb == "1-1"
    assert records[0].nombre == "Palacio"
    assert records[1].cod_disb == "1-2"
    assert records[1].nombre == "Embajadores"


def test_geometry_is_polygon() -> None:
    shp, dbf = _build_shp_dbf([("1-1", "Palacio", _SAMPLE_POLYGON)])

    records = parse_barrios(shp, dbf)

    assert len(records) == 1
    assert records[0].geometry.geom_type == "Polygon"
    assert records[0].geometry.is_valid


def test_missing_cod_disb_is_skipped() -> None:
    shp, dbf = _build_shp_dbf(
        [
            ("", "Palacio", _SAMPLE_POLYGON),
            ("1-2", "Embajadores", _SAMPLE_POLYGON),
        ]
    )

    records = parse_barrios(shp, dbf)

    assert len(records) == 1
    assert records[0].cod_disb == "1-2"


def test_missing_nombre_is_skipped() -> None:
    shp, dbf = _build_shp_dbf(
        [
            ("1-1", "", _SAMPLE_POLYGON),
            ("1-2", "Embajadores", _SAMPLE_POLYGON),
        ]
    )

    records = parse_barrios(shp, dbf)

    assert len(records) == 1
    assert records[0].cod_disb == "1-2"


# ---------------------------------------------------------------------------
# SSRF hostname allowlist
# ---------------------------------------------------------------------------
#
# fetch_barrios_zip delegates the generic hostname-check/download/extract
# logic to shapefile_zip.py (tested exhaustively in test_shapefile_zip.py) —
# these tests just confirm this module wires that shared helper with its own
# URL/allowlist correctly.


def test_fetch_barrios_zip_rejects_disallowed_hostname() -> None:
    """
    fetch_barrios_zip must reject URLs outside the geoportal.madrid.es
    allowlist before making any network call.
    """
    with pytest.raises(ValueError, match="allowed list"):
        fetch_barrios_zip("https://evil.example.com/Barrios.zip")


def test_fetch_barrios_zip_accepts_allowed_hostname() -> None:
    """fetch_barrios_zip must accept geoportal.madrid.es URLs (no ValueError raised)."""
    response = MagicMock()
    response.is_success = True
    response.content = b"zip-bytes"

    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.return_value = response

        content = fetch_barrios_zip("https://geoportal.madrid.es/fsdescargas/Barrios.zip")

    assert content == b"zip-bytes"
