"""
Unit tests for MadridSerCallesProvider.get_records() / _parse().

HTTP layer is exercised via mock so tests run without network access.
Parsing logic is also tested through the private _parse() method directly,
since it's the most complex surface and benefits from isolated exercising.
"""

import textwrap
from unittest.mock import MagicMock, patch

import pytest

from mobility_manager.infrastructure.parking_services.madrid.ser_calles_provider import (
    MadridSerCallesProvider,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider() -> MadridSerCallesProvider:
    return MadridSerCallesProvider(url="https://datos.madrid.es/fake.csv")


# Minimal CSV text that contains valid Madrid coordinates (near Puerta del Sol).
# UTM EPSG:25830: X≈440594, Y≈4474469  →  WGS84 lat≈40.4168, lng≈-3.7038
_BASE_CSV = textwrap.dedent("""\
    calle;color;gis_x;gis_y;numero_plazas
    CALLE MAYOR;043000255 Azul;440594.0;4474469.0;15
""")


# ---------------------------------------------------------------------------
# Parsing: colour / zone type
# ---------------------------------------------------------------------------


def test_rgb_prefix_stripped_and_zone_type_resolved() -> None:
    provider = _make_provider()
    records = provider._parse(_BASE_CSV)

    assert len(records) == 1
    assert records[0].zone_type == "Azul"


def test_alta_rotacion_rgb_prefix_stripped() -> None:
    csv_text = textwrap.dedent("""\
        calle;color;gis_x;gis_y;numero_plazas
        CALLE TEST;081209246 Alta Rotación;440594.0;4474469.0;5
    """)
    provider = _make_provider()
    records = provider._parse(csv_text)

    assert len(records) == 1
    assert records[0].zone_type == "Alta Rotación"


def test_unrecognised_zone_type_skips_row() -> None:
    csv_text = textwrap.dedent("""\
        calle;color;gis_x;gis_y;numero_plazas
        CALLE MAYOR;043000255 Azul;440594.0;4474469.0;15
        CALLE BAD;999999999 Unknown;440594.0;4474469.0;10
    """)
    provider = _make_provider()
    records = provider._parse(csv_text)

    assert len(records) == 1
    assert records[0].street_name == "CALLE MAYOR"


# ---------------------------------------------------------------------------
# Parsing: coordinates
# ---------------------------------------------------------------------------


def test_coordinates_not_divided_by_100() -> None:
    """gis_x / gis_y are direct metres — no ÷100 conversion."""
    provider = _make_provider()
    records = provider._parse(_BASE_CSV)

    assert len(records) == 1
    # utm_x should be the parsed float directly
    assert records[0].utm_x == pytest.approx(440594.0)
    assert records[0].utm_y == pytest.approx(4474469.0)


def test_wgs84_coordinates_are_reprojected() -> None:
    """Reprojected WGS84 coordinates should be inside Madrid bbox."""
    provider = _make_provider()
    records = provider._parse(_BASE_CSV)

    assert len(records) == 1
    assert 40.3 <= records[0].latitude <= 40.6
    assert -3.8 <= records[0].longitude <= -3.6


# ---------------------------------------------------------------------------
# Parsing: spot count
# ---------------------------------------------------------------------------


def test_numeric_spot_count_is_parsed() -> None:
    provider = _make_provider()
    records = provider._parse(_BASE_CSV)

    assert len(records) == 1
    assert records[0].spot_count == 15


def test_missing_numero_plazas_yields_minus_one_not_skipped() -> None:
    csv_text = textwrap.dedent("""\
        calle;color;gis_x;gis_y;numero_plazas
        CALLE MAYOR;043000255 Azul;440594.0;4474469.0;
    """)
    provider = _make_provider()
    records = provider._parse(csv_text)

    assert len(records) == 1
    assert records[0].spot_count == -1


def test_empty_numero_plazas_yields_minus_one_not_skipped() -> None:
    # Column present but blank
    csv_text = textwrap.dedent("""\
        calle;color;gis_x;gis_y;numero_plazas
        CALLE MAYOR;043000255 Azul;440594.0;4474469.0;
    """)
    provider = _make_provider()
    records = provider._parse(csv_text)

    assert records[0].spot_count == -1


def test_non_numeric_numero_plazas_yields_minus_one_not_skipped() -> None:
    csv_text = textwrap.dedent("""\
        calle;color;gis_x;gis_y;numero_plazas
        CALLE MAYOR;043000255 Azul;440594.0;4474469.0;N/A
    """)
    provider = _make_provider()
    records = provider._parse(csv_text)

    assert len(records) == 1
    assert records[0].spot_count == -1


# ---------------------------------------------------------------------------
# Parsing: mandatory field validation
# ---------------------------------------------------------------------------


def test_row_missing_calle_is_skipped() -> None:
    csv_text = textwrap.dedent("""\
        calle;color;gis_x;gis_y;numero_plazas
        ;043000255 Azul;440594.0;4474469.0;10
    """)
    provider = _make_provider()
    records = provider._parse(csv_text)

    assert len(records) == 0


def test_row_missing_color_is_skipped() -> None:
    csv_text = textwrap.dedent("""\
        calle;color;gis_x;gis_y;numero_plazas
        CALLE MAYOR;;440594.0;4474469.0;10
    """)
    provider = _make_provider()
    records = provider._parse(csv_text)

    assert len(records) == 0


def test_row_missing_gis_x_is_skipped() -> None:
    csv_text = textwrap.dedent("""\
        calle;color;gis_x;gis_y;numero_plazas
        CALLE MAYOR;043000255 Azul;;4474469.0;10
    """)
    provider = _make_provider()
    records = provider._parse(csv_text)

    assert len(records) == 0


def test_row_missing_gis_y_is_skipped() -> None:
    csv_text = textwrap.dedent("""\
        calle;color;gis_x;gis_y;numero_plazas
        CALLE MAYOR;043000255 Azul;440594.0;;10
    """)
    provider = _make_provider()
    records = provider._parse(csv_text)

    assert len(records) == 0


# ---------------------------------------------------------------------------
# get_records: HTTP layer
# ---------------------------------------------------------------------------


def test_get_records_fetches_via_http_and_parses() -> None:
    """get_records() calls HTTP and delegates to _parse()."""
    provider = _make_provider()

    fake_response = MagicMock()
    fake_response.is_success = True
    fake_response.content = _BASE_CSV.encode("latin-1")

    with patch("httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.return_value = fake_response
        records = provider.get_records()

    assert len(records) == 1
    assert records[0].street_name == "CALLE MAYOR"
    assert records[0].zone_type == "Azul"


def test_get_records_raises_on_non_2xx() -> None:
    provider = _make_provider()

    fake_response = MagicMock()
    fake_response.is_success = False
    fake_response.status_code = 503

    with patch("httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.return_value = fake_response
        with pytest.raises(RuntimeError, match="503"):
            provider.get_records()


# ---------------------------------------------------------------------------
# Constructor: URL allowlist
# ---------------------------------------------------------------------------


def test_constructor_rejects_non_madrid_url() -> None:
    with pytest.raises(ValueError, match="allowed list"):
        MadridSerCallesProvider(url="https://evil.example.com/data.csv")
