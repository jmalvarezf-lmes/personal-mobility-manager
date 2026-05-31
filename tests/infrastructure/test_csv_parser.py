"""Unit tests for CallejeroCsvParser."""
import textwrap

import pytest

from mobility_manager.infrastructure.parking_services.madrid.csv_parser import (
    CallejeroCsvParser,
    SerZoneRecord,
)

# A minimal valid CSV row using the expected column names.
# UTM Zone 30N coordinates near Puerta del Sol (Madrid).
_VALID_CSV = textwrap.dedent("""\
    NOMBRE_VIA;COD_SER;COORD_X_ETRS89;COORD_Y_ETRS89
    CALLE MAYOR;SER-A;440594;4474469
""")

_MISSING_ZONE_CSV = textwrap.dedent("""\
    NOMBRE_VIA;COD_SER;COORD_X_ETRS89;COORD_Y_ETRS89
    CALLE MAYOR;;440594;4474469
""")

_INVALID_COORD_CSV = textwrap.dedent("""\
    NOMBRE_VIA;COD_SER;COORD_X_ETRS89;COORD_Y_ETRS89
    CALLE MAYOR;SER-A;NOT_A_NUMBER;4474469
""")


def test_valid_row_parses_correctly() -> None:
    parser = CallejeroCsvParser()
    records, skipped = parser.parse(_VALID_CSV)

    assert skipped == 0
    assert len(records) == 1
    record = records[0]
    assert isinstance(record, SerZoneRecord)
    assert record.street_name == "CALLE MAYOR"
    assert record.zone_code == "SER-A"
    assert record.zone_label == "Blue"
    assert isinstance(record.latitude, float)
    assert isinstance(record.longitude, float)
    # Should be in the Madrid WGS84 bounding box
    assert 39.8 <= record.latitude <= 41.2
    assert -4.6 <= record.longitude <= -2.9


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
    records, skipped = parser.parse("NOMBRE_VIA;COD_SER;COORD_X_ETRS89;COORD_Y_ETRS89\n")

    assert records == []
    assert skipped == 0


def test_unknown_zone_code_uses_raw_code_as_label() -> None:
    csv_text = textwrap.dedent("""\
        NOMBRE_VIA;COD_SER;COORD_X_ETRS89;COORD_Y_ETRS89
        CALLE MAYOR;UNKNOWN_CODE;440594;4474469
    """)
    parser = CallejeroCsvParser()
    records, _ = parser.parse(csv_text)

    assert len(records) == 1
    assert records[0].zone_label == "UNKNOWN_CODE"
