"""Unit tests for CallejeroCsvParser."""
import textwrap

import pytest

from mobility_manager.infrastructure.parking_services.madrid.csv_parser import (
    CallejeroCsvParser,
    SerZoneRecord,
)

# Minimal valid CSV using the actual column names from 200075-1-callejero-csv.csv.
# Coordinates near Puerta del Sol (Madrid):
#   UTM Zone 30N (EPSG:25830): X ≈ 440594 m, Y ≈ 4474469 m
#   Stored in the file as centimetres: 44059400, 447446900
_VALID_CSV = textwrap.dedent("""\
    "Nombre de la vía";"Zona Servicio Estacionamiento Regulado";"Coordenada X (Guia Urbana) cm";"Coordenada Y (Guia Urbana) cm"
    "CALLE MAYOR";"011";"0044059400";"0447446900"
""")

_ZONE_000_CSV = textwrap.dedent("""\
    "Nombre de la vía";"Zona Servicio Estacionamiento Regulado";"Coordenada X (Guia Urbana) cm";"Coordenada Y (Guia Urbana) cm"
    "CALLE MAYOR";"000";"0044059400";"0447446900"
""")

_MISSING_ZONE_CSV = textwrap.dedent("""\
    "Nombre de la vía";"Zona Servicio Estacionamiento Regulado";"Coordenada X (Guia Urbana) cm";"Coordenada Y (Guia Urbana) cm"
    "CALLE MAYOR";"";"0044059400";"0447446900"
""")

_INVALID_COORD_CSV = textwrap.dedent("""\
    "Nombre de la vía";"Zona Servicio Estacionamiento Regulado";"Coordenada X (Guia Urbana) cm";"Coordenada Y (Guia Urbana) cm"
    "CALLE MAYOR";"011";"NOT_A_NUMBER";"0447446900"
""")


def test_valid_row_parses_correctly() -> None:
    parser = CallejeroCsvParser()
    records, skipped = parser.parse(_VALID_CSV)

    assert skipped == 0
    assert len(records) == 1
    record = records[0]
    assert isinstance(record, SerZoneRecord)
    assert record.street_name == "CALLE MAYOR"
    assert record.zone_code == "011"
    assert record.zone_label == "011"
    # UTM metres (cm / 100)
    assert record.utm_x == pytest.approx(440594.0)
    assert record.utm_y == pytest.approx(4474469.0)
    # WGS84 should be inside the Madrid bounding box
    assert 39.8 <= record.latitude <= 41.2
    assert -4.6 <= record.longitude <= -2.9


def test_zone_000_row_is_skipped() -> None:
    parser = CallejeroCsvParser()
    records, skipped = parser.parse(_ZONE_000_CSV)

    assert len(records) == 0
    assert skipped == 1


def test_row_with_empty_zone_code_is_skipped() -> None:
    parser = CallejeroCsvParser()
    records, skipped = parser.parse(_MISSING_ZONE_CSV)

    assert len(records) == 0
    assert skipped == 1


def test_row_with_non_numeric_x_coord_is_skipped() -> None:
    parser = CallejeroCsvParser()
    records, skipped = parser.parse(_INVALID_COORD_CSV)

    assert len(records) == 0
    assert skipped == 1


def test_empty_csv_returns_no_records() -> None:
    parser = CallejeroCsvParser()
    records, skipped = parser.parse(
        '"Nombre de la vía";"Zona Servicio Estacionamiento Regulado";'
        '"Coordenada X (Guia Urbana) cm";"Coordenada Y (Guia Urbana) cm"\n'
    )

    assert records == []
    assert skipped == 0


def test_zone_code_used_as_label() -> None:
    """Numeric zone codes are used as-is for zone_label (no colour mapping)."""
    csv_text = textwrap.dedent("""\
        "Nombre de la vía";"Zona Servicio Estacionamiento Regulado";"Coordenada X (Guia Urbana) cm";"Coordenada Y (Guia Urbana) cm"
        "CALLE MAYOR";"042";"0044059400";"0447446900"
    """)
    parser = CallejeroCsvParser()
    records, _ = parser.parse(csv_text)

    assert len(records) == 1
    assert records[0].zone_code == "042"
    assert records[0].zone_label == "042"


def test_column_detection_is_accent_insensitive() -> None:
    """detect_columns matches headers regardless of accent encoding."""
    headers = ["Nombre de la via", "Zona Servicio Estacionamiento Regulado",
               "Coordenada X (Guia Urbana) cm", "Coordenada Y (Guia Urbana) cm"]
    resolved = CallejeroCsvParser.detect_columns(headers)

    assert resolved["street"] is not None
    assert resolved["zone"] is not None
    assert resolved["x"] is not None
    assert resolved["y"] is not None
