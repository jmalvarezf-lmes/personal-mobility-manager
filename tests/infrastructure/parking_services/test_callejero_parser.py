"""
Unit tests for the Madrid callejero CSV parser.

Uses the double-space column names ("...WGS84  " style) and both "º"/"°"
degree-symbol variants exactly as seen in the real source file.
"""

import textwrap

import pytest

from mobility_manager.infrastructure.parking_services.madrid.callejero_parser import (
    parse_callejero_csv,
    parse_dms,
)

_HEADER = (
    "Nombre de la vía;Zona Servicio Estacionamiento Regulado;Nombre del distrito;"
    "Longitud en S R  ETRS89 WGS84;Latitud en S R  ETRS89 WGS84"
)


def _row(street: str, zone: str, district: str, lng: str, lat: str) -> str:
    return f"{street};{zone};{district};{lng};{lat}"


# ---------------------------------------------------------------------------
# DMS parsing
# ---------------------------------------------------------------------------


def test_parse_dms_masculine_ordinal_symbol() -> None:
    # "º" (masculine ordinal indicator) — the actual symbol in the real file.
    result = parse_dms("3º42'14.2'' W")
    assert result == pytest.approx(-3.70394, abs=1e-4)


def test_parse_dms_degree_sign_variant() -> None:
    result = parse_dms("3°42'14.2'' W")
    assert result == pytest.approx(-3.70394, abs=1e-4)


def test_parse_dms_north_hemisphere_is_positive() -> None:
    result = parse_dms("40º25'0.5'' N")
    assert result == pytest.approx(40.41681, abs=1e-4)


def test_parse_dms_returns_none_for_empty() -> None:
    assert parse_dms("") is None


def test_parse_dms_returns_none_for_garbage() -> None:
    assert parse_dms("not a coordinate") is None


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------


def test_known_row_parses_expected_fields() -> None:
    csv_text = textwrap.dedent(
        f"""\
        {_HEADER}
        {_row("ABADA", "163", "CENTRO", "3º42'14.2'' W", "40º25'0.5'' N")}
        """
    )
    points = parse_callejero_csv(csv_text)

    assert len(points) == 1
    point = points[0]
    assert point.street_name == "ABADA"
    assert point.zone_number == "163"
    assert point.district == "CENTRO"
    assert point.lat == pytest.approx(40.41681, abs=1e-4)
    assert point.lng == pytest.approx(-3.70394, abs=1e-4)
    # UTM 25830 near Puerta del Sol, consistent with values used elsewhere in the test suite.
    assert point.utm_x == pytest.approx(440594.0, abs=1000.0)
    assert point.utm_y == pytest.approx(4474469.0, abs=1000.0)


def test_row_missing_street_name_is_skipped() -> None:
    csv_text = textwrap.dedent(
        f"""\
        {_HEADER}
        {_row("", "163", "CENTRO", "3º42'14.2'' W", "40º25'0.5'' N")}
        """
    )
    assert parse_callejero_csv(csv_text) == []


def test_row_missing_zone_number_is_skipped() -> None:
    csv_text = textwrap.dedent(
        f"""\
        {_HEADER}
        {_row("ABADA", "", "CENTRO", "3º42'14.2'' W", "40º25'0.5'' N")}
        """
    )
    assert parse_callejero_csv(csv_text) == []


def test_row_with_unparseable_coordinates_is_skipped() -> None:
    csv_text = textwrap.dedent(
        f"""\
        {_HEADER}
        {_row("ABADA", "163", "CENTRO", "garbage", "40º25'0.5'' N")}
        """
    )
    assert parse_callejero_csv(csv_text) == []


def test_row_with_zone_number_000_is_skipped() -> None:
    # "000" is Madrid's callejero code meaning "not part of any SER zone" —
    # otherwise-valid rows with this code must be excluded, not treated as a
    # real zone.
    csv_text = textwrap.dedent(
        f"""\
        {_HEADER}
        {_row("ABADA", "000", "CENTRO", "3º42'14.2'' W", "40º25'0.5'' N")}
        """
    )
    assert parse_callejero_csv(csv_text) == []


def test_row_with_real_zone_number_is_kept() -> None:
    csv_text = textwrap.dedent(
        f"""\
        {_HEADER}
        {_row("ABADA", "163", "CENTRO", "3º42'14.2'' W", "40º25'0.5'' N")}
        """
    )
    points = parse_callejero_csv(csv_text)
    assert len(points) == 1
    assert points[0].zone_number == "163"


def test_multiple_rows_parsed() -> None:
    csv_text = textwrap.dedent(
        f"""\
        {_HEADER}
        {_row("ABADA", "163", "CENTRO", "3º42'14.2'' W", "40º25'0.5'' N")}
        {_row("GRAN VIA", "164", "CENTRO", "3°42'20.0'' W", "40°25'5.0'' N")}
        """
    )
    points = parse_callejero_csv(csv_text)
    assert len(points) == 2
    assert {p.street_name for p in points} == {"ABADA", "GRAN VIA"}
