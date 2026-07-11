"""
Unit tests for SER band shapefile parsing.

Builds small synthetic in-memory .shp/.dbf fixtures via pyshp's Writer
(no network access, no real Madrid data needed) — shape_type=3 (PolyLine),
fields ID (numeric), Color (text), Res_NumPla (numeric), matching the real
SER_BANDA_APARCAMIENTO schema. Bateria_Li is deliberately not part of the
fixture since it is never parsed (design.md D4).
"""

import io

import pytest
import shapefile

from mobility_manager.infrastructure.parking_services.madrid.ser_band_shapefile import (
    fetch_ser_band_zip,
    parse_ser_bands,
)


def _build_shp_dbf(rows: list[tuple[int, str, int, list[tuple[float, float]]]]) -> tuple[io.BytesIO, io.BytesIO]:
    """
    Build in-memory .shp/.dbf streams for the given (id, color, spot_count, points) rows.
    """
    shp = io.BytesIO()
    dbf = io.BytesIO()
    writer = shapefile.Writer(shp=shp, dbf=dbf, shapeType=shapefile.POLYLINE)
    writer.field("ID", "N")
    writer.field("Color", "C")
    writer.field("Res_NumPla", "N")

    for feature_id, color, spot_count, points in rows:
        writer.line([[[x, y] for x, y in points]])
        writer.record(feature_id, color, spot_count)

    writer.close()
    shp.seek(0)
    dbf.seek(0)
    return shp, dbf


_SAMPLE_LINE = [(440590.0, 4474460.0), (440600.0, 4474470.0)]


def test_sample_rows_parse_expected_values() -> None:
    shp, dbf = _build_shp_dbf(
        [
            (1, "Azul", 5, _SAMPLE_LINE),
            (2, "Verde", 3, _SAMPLE_LINE),
        ]
    )

    bands = parse_ser_bands(shp, dbf)

    assert len(bands) == 2
    assert bands[0].zone_type == "Azul"
    assert bands[0].spot_count == 5
    assert bands[1].zone_type == "Verde"
    assert bands[1].spot_count == 3


def test_gris_rows_are_excluded() -> None:
    shp, dbf = _build_shp_dbf(
        [
            (1, "Azul", 5, _SAMPLE_LINE),
            (2, "Gris", -1, _SAMPLE_LINE),
        ]
    )

    bands = parse_ser_bands(shp, dbf)

    assert len(bands) == 1
    assert bands[0].zone_type == "Azul"


def test_unrecognised_color_is_skipped() -> None:
    shp, dbf = _build_shp_dbf(
        [
            (1, "Azul", 5, _SAMPLE_LINE),
            (2, "Morado", 5, _SAMPLE_LINE),
        ]
    )

    bands = parse_ser_bands(shp, dbf)

    assert len(bands) == 1
    assert bands[0].zone_type == "Azul"


def test_missing_spot_count_yields_minus_one() -> None:
    shp = io.BytesIO()
    dbf = io.BytesIO()
    writer = shapefile.Writer(shp=shp, dbf=dbf, shapeType=shapefile.POLYLINE)
    writer.field("ID", "N")
    writer.field("Color", "C")
    writer.field("Res_NumPla", "N")
    writer.line([[[x, y] for x, y in _SAMPLE_LINE]])
    writer.record(1, "Azul", None)
    writer.close()
    shp.seek(0)
    dbf.seek(0)

    bands = parse_ser_bands(shp, dbf)

    assert len(bands) == 1
    assert bands[0].spot_count == -1


def test_geometry_is_linestring_with_expected_points() -> None:
    shp, dbf = _build_shp_dbf([(1, "Azul", 5, _SAMPLE_LINE)])

    bands = parse_ser_bands(shp, dbf)

    assert len(bands) == 1
    coords = list(bands[0].geometry.coords)
    assert coords == [(440590.0, 4474460.0), (440600.0, 4474470.0)]


# ---------------------------------------------------------------------------
# SSRF hostname allowlist
# ---------------------------------------------------------------------------


def test_fetch_ser_band_zip_rejects_disallowed_hostname() -> None:
    """
    fetch_ser_band_zip must reject URLs outside the geoportal.madrid.es
    allowlist before making any network call.
    """
    with pytest.raises(ValueError, match="allowed list"):
        fetch_ser_band_zip("https://evil.example.com/SHP_ZIP.zip")
