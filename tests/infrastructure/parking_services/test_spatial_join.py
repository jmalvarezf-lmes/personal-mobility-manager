"""Unit tests for the SER band <-> callejero spatial join."""

from shapely.geometry import LineString

from mobility_manager.infrastructure.parking_services.madrid.callejero_parser import (
    CallejeroPoint,
)
from mobility_manager.infrastructure.parking_services.madrid.ser_band_shapefile import (
    SerBand,
)
from mobility_manager.infrastructure.parking_services.madrid.spatial_join import (
    join_bands_to_callejero,
)


def _make_point(
    zone_number: str,
    street_name: str,
    district: str,
    utm_x: float,
    utm_y: float,
    district_code: str = "01",
    barrio_code: str = "06",
) -> CallejeroPoint:
    return CallejeroPoint(
        zone_number=zone_number,
        street_name=street_name,
        district=district,
        district_code=district_code,
        barrio_code=barrio_code,
        lat=40.4168,
        lng=-3.7038,
        utm_x=utm_x,
        utm_y=utm_y,
    )


def _make_band(utm_x: float, utm_y: float, dx: float = 10.0) -> SerBand:
    return SerBand(
        zone_type="Azul",
        spot_count=5,
        geometry=LineString([(utm_x, utm_y), (utm_x + dx, utm_y)]),
    )


def test_band_inherits_nearest_callejero_point() -> None:
    near_point = _make_point("163", "ABADA", "CENTRO", utm_x=440590.0, utm_y=4474460.0)
    far_point = _make_point("999", "FAR STREET", "OTHER", utm_x=500000.0, utm_y=4500000.0)

    band = _make_band(utm_x=440590.0, utm_y=4474460.0)

    joined = join_bands_to_callejero([band], [near_point, far_point])

    assert len(joined) == 1
    assert joined[0].zone_number == "163"
    assert joined[0].street_name == "ABADA"
    assert joined[0].district == "CENTRO"


def test_band_inherits_nearest_callejero_points_district_and_barrio_code() -> None:
    near_point = _make_point(
        "163", "ABADA", "CENTRO", utm_x=440590.0, utm_y=4474460.0, district_code="01", barrio_code="06"
    )
    band = _make_band(utm_x=440590.0, utm_y=4474460.0)

    joined = join_bands_to_callejero([band], [near_point])

    assert len(joined) == 1
    assert joined[0].district_code == "01"
    assert joined[0].barrio_code == "06"


def test_multiple_bands_each_join_independently() -> None:
    point_a = _make_point("163", "ABADA", "CENTRO", utm_x=440590.0, utm_y=4474460.0)
    point_b = _make_point("200", "GRAN VIA", "CENTRO", utm_x=441000.0, utm_y=4474900.0)

    band_near_a = _make_band(utm_x=440590.0, utm_y=4474460.0)
    band_near_b = _make_band(utm_x=441000.0, utm_y=4474900.0)

    joined = join_bands_to_callejero([band_near_a, band_near_b], [point_a, point_b])

    assert len(joined) == 2
    zone_numbers = {j.zone_number for j in joined}
    assert zone_numbers == {"163", "200"}


def test_empty_callejero_points_returns_empty_list() -> None:
    band = _make_band(utm_x=440590.0, utm_y=4474460.0)
    joined = join_bands_to_callejero([band], [])
    assert joined == []
