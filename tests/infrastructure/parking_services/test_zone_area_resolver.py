"""
Unit tests for zone_number -> ZoneArea (frontier) resolution via
compound-code majority vote + Barrios lookup.
"""

from shapely.geometry import LineString, Polygon

from mobility_manager.infrastructure.parking_services.madrid.barrios_shapefile import (
    BarrioRecord,
)
from mobility_manager.infrastructure.parking_services.madrid.ser_band_shapefile import (
    SerBand,
)
from mobility_manager.infrastructure.parking_services.madrid.spatial_join import (
    JoinedBand,
)
from mobility_manager.infrastructure.parking_services.madrid.zone_area_resolver import (
    compute_majority_compound_codes,
    resolve_zone_areas,
)

_PALACIO_POLYGON = Polygon([(440000, 4474000), (440100, 4474000), (440100, 4474100), (440000, 4474100)])
_SOL_POLYGON = Polygon([(441000, 4475000), (441100, 4475000), (441100, 4475100), (441000, 4475100)])


def _band(zone_number: str, district_code: str, barrio_code: str, x: float = 0.0, y: float = 0.0) -> JoinedBand:
    return JoinedBand(
        band=SerBand(zone_type="Azul", spot_count=1, geometry=LineString([(x, y), (x + 10, y)])),
        zone_number=zone_number,
        street_name="ABADA",
        district="CENTRO",
        district_code=district_code,
        barrio_code=barrio_code,
    )


def test_majority_compound_code_resolves_to_matching_barrio() -> None:
    bands = [
        _band("163", "01", "06"),
        _band("163", "01", "06"),
        _band("163", "01", "03"),
    ]
    barrios = [
        BarrioRecord(cod_disb="1-6", nombre="Sol", geometry=_SOL_POLYGON),
        BarrioRecord(cod_disb="1-3", nombre="Cortes", geometry=_PALACIO_POLYGON),
    ]

    zone_areas = resolve_zone_areas(bands, barrios, "madrid")

    assert len(zone_areas) == 1
    assert zone_areas[0].zone_number == "163"
    assert zone_areas[0].neighbourhood == "Sol"
    assert zone_areas[0].geometry == _SOL_POLYGON


def test_unresolvable_zone_number_is_skipped() -> None:
    bands = [_band("999", "99", "99")]
    barrios = [BarrioRecord(cod_disb="1-6", nombre="Sol", geometry=_SOL_POLYGON)]

    zone_areas = resolve_zone_areas(bands, barrios, "madrid")

    assert zone_areas == []


def test_two_zone_numbers_sharing_compound_code_produce_identical_geometry() -> None:
    bands = [
        _band("163", "01", "06"),
        _band("200", "01", "06"),
    ]
    barrios = [BarrioRecord(cod_disb="1-6", nombre="Sol", geometry=_SOL_POLYGON)]

    zone_areas = resolve_zone_areas(bands, barrios, "madrid")

    assert len(zone_areas) == 2
    zone_numbers = {za.zone_number for za in zone_areas}
    assert zone_numbers == {"163", "200"}
    for za in zone_areas:
        assert za.neighbourhood == "Sol"
        assert za.geometry == _SOL_POLYGON


def test_official_nombre_used_verbatim_not_derived_from_callejero() -> None:
    """
    The resolved neighbourhood must be the Barrios record's own NOMBRE, not
    any string derived from the callejero's own barrio name field — there is
    no callejero barrio-name field anywhere in this resolution path at all
    (JoinedBand carries no barrio-name field, only numeric codes).
    """
    bands = [_band("163", "01", "06")]
    barrios = [BarrioRecord(cod_disb="1-6", nombre="Sol", geometry=_SOL_POLYGON)]

    zone_areas = resolve_zone_areas(bands, barrios, "madrid")

    assert len(zone_areas) == 1
    assert zone_areas[0].neighbourhood == "Sol"
    assert not hasattr(bands[0], "barrio_name")


def test_compute_majority_compound_codes_deterministic_tie_break() -> None:
    bands = [
        _band("163", "01", "06"),
        _band("163", "01", "03"),
    ]
    result = compute_majority_compound_codes(bands)
    # Counter.most_common() is stable: first-inserted key among ties wins.
    assert result["163"] == "1-6"


def test_compute_majority_compound_codes_strips_zero_padding() -> None:
    bands = [_band("163", "01", "06")]
    result = compute_majority_compound_codes(bands)
    assert result["163"] == "1-6"


def test_non_numeric_codes_excluded_from_vote() -> None:
    bands = [_band("163", "garbage", "06")]
    result = compute_majority_compound_codes(bands)
    assert "163" not in result


def test_empty_bands_returns_empty_result() -> None:
    assert resolve_zone_areas([], [], "madrid") == []
    assert compute_majority_compound_codes([]) == {}
