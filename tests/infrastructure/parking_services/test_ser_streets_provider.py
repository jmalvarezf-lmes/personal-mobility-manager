"""
Integration test for MadridSerStreetsProvider.get_records() end to end.

Both HTTP sources (SER band shapefile zip, callejero CSV) are mocked with
small synthetic fixtures so this runs with no network access.
"""

import io
import textwrap
import zipfile
from unittest.mock import MagicMock, patch

import pytest
import shapefile

from mobility_manager.infrastructure.parking_services.madrid.ser_streets_provider import (
    MadridSerStreetsProvider,
)

_CALLEJERO_HEADER = (
    "Nombre de la vía;Zona Servicio Estacionamiento Regulado;Nombre del distrito;"
    "Longitud en S R  ETRS89 WGS84;Latitud en S R  ETRS89 WGS84"
)

_CALLEJERO_CSV = textwrap.dedent(
    f"""\
    {_CALLEJERO_HEADER}
    ABADA;163;CENTRO;3º42'14.2'' W;40º25'0.5'' N
    """
)

# Band midpoint deliberately close to the callejero point above so the
# nearest-neighbour join is deterministic in this small fixture.
_BAND_LINE = [(440590.0, 4474460.0), (440600.0, 4474470.0)]

# Same callejero CSV as above, plus a "000" (non-SER) row placed almost
# exactly at the band's own midpoint (440595.0, 4474465.0 in EPSG:25830) —
# i.e. much closer to the band than the real "163" address point (~378m
# away). If "000" rows were (incorrectly) included in the join index, the
# band would wrongly inherit zone_number "000" instead of "163" — this
# fixture proves the "000" row is excluded end to end even though it is the
# geographically nearer candidate.
_CALLEJERO_CSV_WITH_NON_SER_ROW = textwrap.dedent(
    f"""\
    {_CALLEJERO_HEADER}
    NEARBY NON-SER STREET;000;CENTRO;3º42'0.8'' W;40º25'7.3'' N
    ABADA;163;CENTRO;3º42'14.2'' W;40º25'0.5'' N
    """
)


def _build_shp_zip() -> bytes:
    shp = io.BytesIO()
    dbf = io.BytesIO()
    writer = shapefile.Writer(shp=shp, dbf=dbf, shapeType=shapefile.POLYLINE)
    writer.field("ID", "N")
    writer.field("Color", "C")
    writer.field("Res_NumPla", "N")
    writer.line([[[x, y] for x, y in _BAND_LINE]])
    writer.record(1, "Azul", 5)
    writer.close()
    shp.seek(0)
    dbf.seek(0)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        archive.writestr("SER_BANDA_APARCAMIENTO.shp", shp.getvalue())
        archive.writestr("SER_BANDA_APARCAMIENTO.dbf", dbf.getvalue())
    return zip_buffer.getvalue()


def test_get_records_returns_expected_zone_boundary_records() -> None:
    provider = MadridSerStreetsProvider(
        shp_url="https://geoportal.madrid.es/fsdescargas/fake.zip",
        callejero_url="https://datos.madrid.es/fake.csv",
    )

    shp_response = MagicMock()
    shp_response.is_success = True
    shp_response.content = _build_shp_zip()

    csv_response = MagicMock()
    csv_response.is_success = True
    csv_response.content = _CALLEJERO_CSV.encode("latin-1")

    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.side_effect = [shp_response, csv_response]

        records = provider.get_records()

    assert len(records) == 1
    record = records[0]
    assert record.zone_number == "163"
    assert record.zone_type == "Azul"
    assert record.district == "CENTRO"
    assert record.street_names == ["ABADA"]
    assert record.spot_count == 5
    assert record.geometry.is_valid


def test_get_records_excludes_non_ser_000_row_from_join_even_when_closer() -> None:
    """
    A callejero row with zone_number "000" must never be usable as a join
    target, even when it is geographically closer to a band's midpoint than
    any real SER-zoned address point — the band must still inherit the
    nearest *SER-zoned* point's zone_number.
    """
    provider = MadridSerStreetsProvider(
        shp_url="https://geoportal.madrid.es/fsdescargas/fake.zip",
        callejero_url="https://datos.madrid.es/fake.csv",
    )

    shp_response = MagicMock()
    shp_response.is_success = True
    shp_response.content = _build_shp_zip()

    csv_response = MagicMock()
    csv_response.is_success = True
    csv_response.content = _CALLEJERO_CSV_WITH_NON_SER_ROW.encode("latin-1")

    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.side_effect = [shp_response, csv_response]

        records = provider.get_records()

    assert len(records) == 1
    record = records[0]
    assert record.zone_number == "163"
    assert record.zone_number != "000"
    assert record.street_names == ["ABADA"]


def test_city_code_is_madrid() -> None:
    provider = MadridSerStreetsProvider()
    assert provider.city_code == "madrid"


def test_get_records_raises_when_shp_source_fails() -> None:
    """
    HTTP failure on the SHP source must raise, not be swallowed — the
    ingestion use case relies on this to abort the run.
    """
    provider = MadridSerStreetsProvider(
        shp_url="https://geoportal.madrid.es/fsdescargas/fake.zip",
        callejero_url="https://datos.madrid.es/fake.csv",
    )

    shp_response = MagicMock()
    shp_response.is_success = False
    shp_response.status_code = 503

    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.return_value = shp_response

        with pytest.raises(RuntimeError, match="503"):
            provider.get_records()


def test_get_records_raises_when_callejero_source_fails() -> None:
    """
    HTTP failure on the callejero source must raise, not be swallowed — even
    when the SHP source succeeds first.
    """
    provider = MadridSerStreetsProvider(
        shp_url="https://geoportal.madrid.es/fsdescargas/fake.zip",
        callejero_url="https://datos.madrid.es/fake.csv",
    )

    shp_response = MagicMock()
    shp_response.is_success = True
    shp_response.content = _build_shp_zip()

    callejero_response = MagicMock()
    callejero_response.is_success = False
    callejero_response.status_code = 500

    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.side_effect = [shp_response, callejero_response]

        with pytest.raises(RuntimeError, match="500"):
            provider.get_records()


def test_get_records_uses_configured_urls_instead_of_defaults() -> None:
    """
    When SER_ZONE_SHP_URL / MADRID_CALLEJERO_URL (constructor args here) are
    set, the provider must actually request those URLs, not the defaults.
    """
    custom_shp_url = "https://geoportal.madrid.es/fsdescargas/custom_shp.zip"
    custom_callejero_url = "https://datos.madrid.es/custom_callejero.csv"

    provider = MadridSerStreetsProvider(
        shp_url=custom_shp_url,
        callejero_url=custom_callejero_url,
    )

    shp_response = MagicMock()
    shp_response.is_success = True
    shp_response.content = _build_shp_zip()

    csv_response = MagicMock()
    csv_response.is_success = True
    csv_response.content = _CALLEJERO_CSV.encode("latin-1")

    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.side_effect = [shp_response, csv_response]

        provider.get_records()

        requested_urls = [call.args[0] for call in mock_client.get.call_args_list]

    assert requested_urls == [custom_shp_url, custom_callejero_url]
