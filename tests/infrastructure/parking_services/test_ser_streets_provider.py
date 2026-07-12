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
    "Codigo de distrito;Codigo de barrio;"
    "Longitud en S R  ETRS89 WGS84;Latitud en S R  ETRS89 WGS84"
)

_CALLEJERO_CSV = textwrap.dedent(
    f"""\
    {_CALLEJERO_HEADER}
    ABADA;163;CENTRO;01;06;3º42'14.2'' W;40º25'0.5'' N
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
    NEARBY NON-SER STREET;000;CENTRO;01;06;3º42'0.8'' W;40º25'7.3'' N
    ABADA;163;CENTRO;01;06;3º42'14.2'' W;40º25'0.5'' N
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


# ---------------------------------------------------------------------------
# get_zone_areas()
# ---------------------------------------------------------------------------


def _build_barrios_zip() -> bytes:
    shp = io.BytesIO()
    dbf = io.BytesIO()
    writer = shapefile.Writer(shp=shp, dbf=dbf, shapeType=shapefile.POLYGON)
    writer.field("COD_DISB", "C")
    writer.field("NOMBRE", "C")
    writer.poly([[[440000.0, 4474000.0], [440100.0, 4474000.0], [440100.0, 4474100.0], [440000.0, 4474100.0]]])
    writer.record("1-6", "Sol")
    writer.close()
    shp.seek(0)
    dbf.seek(0)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        archive.writestr("BARRIOS.shp", shp.getvalue())
        archive.writestr("BARRIOS.dbf", dbf.getvalue())
    return zip_buffer.getvalue()


def test_get_zone_areas_returns_one_zone_area_per_resolvable_zone_number() -> None:
    provider = MadridSerStreetsProvider(
        shp_url="https://geoportal.madrid.es/fsdescargas/fake_ser.zip",
        callejero_url="https://datos.madrid.es/fake.csv",
        barrios_shp_url="https://geoportal.madrid.es/fsdescargas/fake_barrios.zip",
    )

    shp_response = MagicMock()
    shp_response.is_success = True
    shp_response.content = _build_shp_zip()

    csv_response = MagicMock()
    csv_response.is_success = True
    csv_response.content = _CALLEJERO_CSV.encode("latin-1")

    barrios_response = MagicMock()
    barrios_response.is_success = True
    barrios_response.content = _build_barrios_zip()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.side_effect = [shp_response, csv_response, barrios_response]

        zone_areas = provider.get_zone_areas()

    assert len(zone_areas) == 1
    zone_area = zone_areas[0]
    assert zone_area.zone_number == "163"
    assert zone_area.neighbourhood == "Sol"
    assert zone_area.geometry.is_valid


def test_get_zone_areas_raises_when_barrios_source_fails() -> None:
    """
    HTTP failure on the Barrios source must raise, not be swallowed — the
    ingestion use case relies on this to abort the run.
    """
    provider = MadridSerStreetsProvider(
        shp_url="https://geoportal.madrid.es/fsdescargas/fake_ser.zip",
        callejero_url="https://datos.madrid.es/fake.csv",
        barrios_shp_url="https://geoportal.madrid.es/fsdescargas/fake_barrios.zip",
    )

    shp_response = MagicMock()
    shp_response.is_success = True
    shp_response.content = _build_shp_zip()

    csv_response = MagicMock()
    csv_response.is_success = True
    csv_response.content = _CALLEJERO_CSV.encode("latin-1")

    barrios_response = MagicMock()
    barrios_response.is_success = False
    barrios_response.status_code = 503

    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.side_effect = [shp_response, csv_response, barrios_response]

        with pytest.raises(RuntimeError, match="503"):
            provider.get_zone_areas()


def test_get_zone_areas_and_get_records_do_not_share_cache() -> None:
    """
    Resilience test (design.md D7): get_records() and get_zone_areas() must
    each independently re-fetch/re-parse everything — no cross-call cache
    that could go stale across scheduled ingestion runs. Calling both in
    sequence must issue fresh HTTP requests for the second call, not reuse
    any state from the first.
    """
    provider = MadridSerStreetsProvider(
        shp_url="https://geoportal.madrid.es/fsdescargas/fake_ser.zip",
        callejero_url="https://datos.madrid.es/fake.csv",
        barrios_shp_url="https://geoportal.madrid.es/fsdescargas/fake_barrios.zip",
    )

    def _fresh_shp_response() -> MagicMock:
        response = MagicMock()
        response.is_success = True
        response.content = _build_shp_zip()
        return response

    def _fresh_csv_response() -> MagicMock:
        response = MagicMock()
        response.is_success = True
        response.content = _CALLEJERO_CSV.encode("latin-1")
        return response

    def _fresh_barrios_response() -> MagicMock:
        response = MagicMock()
        response.is_success = True
        response.content = _build_barrios_zip()
        return response

    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.side_effect = [
            _fresh_shp_response(),
            _fresh_csv_response(),
            _fresh_shp_response(),
            _fresh_csv_response(),
            _fresh_barrios_response(),
        ]

        records = provider.get_records()
        zone_areas = provider.get_zone_areas()

        assert mock_client.get.call_count == 5

    assert len(records) == 1
    assert len(zone_areas) == 1


def test_get_records_and_zone_areas_fetches_each_source_exactly_once() -> None:
    """
    get_records_and_zone_areas() must issue exactly 3 HTTP calls (SER band
    shapefile, callejero CSV, Barrios shapefile) — not 5 — proving it shares
    one fetch of the SER band shapefile/callejero CSV between the records and
    zone_areas halves, instead of calling get_records() then get_zone_areas()
    back to back (which independently re-fetches both per design.md D7).
    """
    provider = MadridSerStreetsProvider(
        shp_url="https://geoportal.madrid.es/fsdescargas/fake_ser.zip",
        callejero_url="https://datos.madrid.es/fake.csv",
        barrios_shp_url="https://geoportal.madrid.es/fsdescargas/fake_barrios.zip",
    )

    shp_response = MagicMock()
    shp_response.is_success = True
    shp_response.content = _build_shp_zip()

    csv_response = MagicMock()
    csv_response.is_success = True
    csv_response.content = _CALLEJERO_CSV.encode("latin-1")

    barrios_response = MagicMock()
    barrios_response.is_success = True
    barrios_response.content = _build_barrios_zip()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.side_effect = [shp_response, csv_response, barrios_response]

        records, zone_areas = provider.get_records_and_zone_areas()

        assert mock_client.get.call_count == 3

    assert len(records) == 1
    assert records[0].zone_number == "163"
    assert len(zone_areas) == 1
    assert zone_areas[0].zone_number == "163"
    assert zone_areas[0].neighbourhood == "Sol"


# ---------------------------------------------------------------------------
# get_records() output freshness across repeated calls (no stale cache)
# ---------------------------------------------------------------------------
#
# The test above only proves *call count* — it cannot distinguish "genuinely
# re-fetched and re-parsed from scratch" from "an internal cache was silently
# populated on the first call and served on the second, while some unrelated
# code path happened to still make N HTTP calls for other reasons". This is
# exactly the class of BLOCKER-severity caching-staleness bug the discarded
# first implementation attempt at this feature had (design.md D7): a provider
# that appeared to make the right number of calls but was secretly serving
# stale cached data across scheduled ingestion runs.
#
# The tests below mock the SECOND set of HTTP responses (simulating a second
# scheduled ingestion run on the same long-lived provider instance) with
# DIFFERENT content than the first set, and assert the second call's actual
# returned data reflects the new content — not the first call's content. This
# directly proves there is no cache serving stale data, rather than inferring
# it indirectly from a call count.

_CALLEJERO_CSV_SECOND_RUN = textwrap.dedent(
    f"""\
    {_CALLEJERO_HEADER}
    GRAN VIA;042;CHAMBERI;05;09;3º42'14.2'' W;40º25'0.5'' N
    """
)


def _build_shp_zip_second_run() -> bytes:
    """
    A distinct SER band shapefile fixture: different Color, spot count, and
    geometry than `_build_shp_zip()`, to prove a second `get_records()` call
    reflects genuinely new data rather than a cached first-call result.
    """
    shp = io.BytesIO()
    dbf = io.BytesIO()
    writer = shapefile.Writer(shp=shp, dbf=dbf, shapeType=shapefile.POLYLINE)
    writer.field("ID", "N")
    writer.field("Color", "C")
    writer.field("Res_NumPla", "N")
    second_run_line = [(440592.0, 4474462.0), (440602.0, 4474472.0)]
    writer.line([[[x, y] for x, y in second_run_line]])
    writer.record(1, "Verde", 9)
    writer.close()
    shp.seek(0)
    dbf.seek(0)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        archive.writestr("SER_BANDA_APARCAMIENTO.shp", shp.getvalue())
        archive.writestr("SER_BANDA_APARCAMIENTO.dbf", dbf.getvalue())
    return zip_buffer.getvalue()


def test_get_records_second_call_reflects_new_mocked_data_not_stale_cache() -> None:
    """
    Calling get_records() twice on the same provider instance, with the
    second round of mocked HTTP responses carrying different content (a
    different zone_number, zone_type, and spot_count), must produce output
    that reflects the SECOND response — proving get_records() genuinely
    re-fetches and re-parses on every call rather than silently serving a
    cached result from the first call while still happening to issue the
    same number of HTTP calls.
    """
    provider = MadridSerStreetsProvider(
        shp_url="https://geoportal.madrid.es/fsdescargas/fake.zip",
        callejero_url="https://datos.madrid.es/fake.csv",
    )

    first_shp_response = MagicMock()
    first_shp_response.is_success = True
    first_shp_response.content = _build_shp_zip()

    first_csv_response = MagicMock()
    first_csv_response.is_success = True
    first_csv_response.content = _CALLEJERO_CSV.encode("latin-1")

    second_shp_response = MagicMock()
    second_shp_response.is_success = True
    second_shp_response.content = _build_shp_zip_second_run()

    second_csv_response = MagicMock()
    second_csv_response.is_success = True
    second_csv_response.content = _CALLEJERO_CSV_SECOND_RUN.encode("latin-1")

    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.side_effect = [
            first_shp_response,
            first_csv_response,
            second_shp_response,
            second_csv_response,
        ]

        first_records = provider.get_records()
        second_records = provider.get_records()

    assert len(first_records) == 1
    assert first_records[0].zone_number == "163"
    assert first_records[0].zone_type == "Azul"
    assert first_records[0].spot_count == 5

    # The second call must reflect the SECOND mocked response's content, not
    # the first call's — this is the assertion a silently-populated cache
    # would fail, even though the call count above would still look correct.
    assert len(second_records) == 1
    assert second_records[0].zone_number == "042"
    assert second_records[0].zone_type == "Verde"
    assert second_records[0].spot_count == 9
    assert second_records[0].zone_number != first_records[0].zone_number


def test_get_zone_areas_second_call_reflects_new_mocked_data_not_stale_cache() -> None:
    """
    Same freshness proof as
    test_get_records_second_call_reflects_new_mocked_data_not_stale_cache,
    but for get_zone_areas(): the second round of mocked Barrios/SER/callejero
    responses carries a different neighbourhood and zone_number, and the
    second call's output must reflect it.
    """
    provider = MadridSerStreetsProvider(
        shp_url="https://geoportal.madrid.es/fsdescargas/fake_ser.zip",
        callejero_url="https://datos.madrid.es/fake.csv",
        barrios_shp_url="https://geoportal.madrid.es/fsdescargas/fake_barrios.zip",
    )

    def _first_run_responses() -> list[MagicMock]:
        shp_response = MagicMock()
        shp_response.is_success = True
        shp_response.content = _build_shp_zip()

        csv_response = MagicMock()
        csv_response.is_success = True
        csv_response.content = _CALLEJERO_CSV.encode("latin-1")

        barrios_response = MagicMock()
        barrios_response.is_success = True
        barrios_response.content = _build_barrios_zip()

        return [shp_response, csv_response, barrios_response]

    def _build_barrios_zip_second_run() -> bytes:
        shp = io.BytesIO()
        dbf = io.BytesIO()
        writer = shapefile.Writer(shp=shp, dbf=dbf, shapeType=shapefile.POLYGON)
        writer.field("COD_DISB", "C")
        writer.field("NOMBRE", "C")
        writer.poly([[[440000.0, 4474000.0], [440100.0, 4474000.0], [440100.0, 4474100.0], [440000.0, 4474100.0]]])
        writer.record("5-9", "Ríos Rosas")
        writer.close()
        shp.seek(0)
        dbf.seek(0)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as archive:
            archive.writestr("BARRIOS.shp", shp.getvalue())
            archive.writestr("BARRIOS.dbf", dbf.getvalue())
        return zip_buffer.getvalue()

    def _second_run_responses() -> list[MagicMock]:
        shp_response = MagicMock()
        shp_response.is_success = True
        shp_response.content = _build_shp_zip_second_run()

        csv_response = MagicMock()
        csv_response.is_success = True
        csv_response.content = _CALLEJERO_CSV_SECOND_RUN.encode("latin-1")

        barrios_response = MagicMock()
        barrios_response.is_success = True
        barrios_response.content = _build_barrios_zip_second_run()

        return [shp_response, csv_response, barrios_response]

    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.side_effect = [*_first_run_responses(), *_second_run_responses()]

        first_zone_areas = provider.get_zone_areas()
        second_zone_areas = provider.get_zone_areas()

    assert len(first_zone_areas) == 1
    assert first_zone_areas[0].zone_number == "163"
    assert first_zone_areas[0].neighbourhood == "Sol"

    # The second call must reflect the SECOND mocked response's content, not
    # the first call's.
    assert len(second_zone_areas) == 1
    assert second_zone_areas[0].zone_number == "042"
    assert second_zone_areas[0].neighbourhood == "Ríos Rosas"
    assert second_zone_areas[0].neighbourhood != first_zone_areas[0].neighbourhood
