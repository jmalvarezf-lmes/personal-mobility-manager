"""Unit tests for SerZone entity."""

import pytest
from shapely.geometry import Polygon

from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.value_objects.location import GeoLocation

# A simple square polygon in EPSG:25830 metres, centred exactly on the
# pyproj-projected UTM coordinates of (lat=40.4168, lng=-3.7038) so WGS84
# test locations round-trip realistically through the same transform used by
# SerZone.contains().
_CENTRE_UTM = (440290.46, 4474257.38)
_SQUARE = Polygon(
    [
        (_CENTRE_UTM[0] - 10.0, _CENTRE_UTM[1] - 10.0),
        (_CENTRE_UTM[0] + 10.0, _CENTRE_UTM[1] - 10.0),
        (_CENTRE_UTM[0] + 10.0, _CENTRE_UTM[1] + 10.0),
        (_CENTRE_UTM[0] - 10.0, _CENTRE_UTM[1] + 10.0),
    ]
)


def _make_ser_zone(**kwargs) -> SerZone:
    defaults = {
        "city_code": "madrid",
        "zone_number": "163",
        "zone_type": "Azul",
        "district": "CENTRO",
        "spot_count": 15,
        "geometry": _SQUARE,
    }
    defaults.update(kwargs)
    return SerZone(**defaults)


def test_ser_zone_construction_with_new_fields() -> None:
    zone = _make_ser_zone()

    assert zone.zone_number == "163"
    assert zone.zone_type == "Azul"
    assert zone.district == "CENTRO"
    assert zone.spot_count == 15
    assert zone.geometry == _SQUARE


def test_ser_zone_carries_and_exposes_city_code() -> None:
    """SerZone must carry city_code so the enforcement check knows which
    city's calendar applies to a matched zone (see
    add-ser-enforcement-calendar design.md D5)."""
    zone = _make_ser_zone(city_code="madrid")
    assert zone.city_code == "madrid"

    other_city_zone = _make_ser_zone(city_code="barcelona")
    assert other_city_zone.city_code == "barcelona"


def test_ser_zone_spot_count_minus_one_for_unknown() -> None:
    zone = _make_ser_zone(spot_count=-1)
    assert zone.spot_count == -1


def test_ser_zone_is_immutable() -> None:
    zone = _make_ser_zone()
    with pytest.raises((AttributeError, TypeError)):
        zone.zone_type = "Verde"  # type: ignore[misc]


def test_ser_zone_no_street_names_attribute() -> None:
    zone = _make_ser_zone()
    assert not hasattr(zone, "street_names"), "street_names must not exist on SerZone (see design.md D9)"


# ---------------------------------------------------------------------------
# contains()
# ---------------------------------------------------------------------------


def test_contains_true_for_interior_point() -> None:
    zone = _make_ser_zone()
    # Centre of the square, well inside the boundary.
    location = GeoLocation(lat=40.4168, lng=-3.7038)
    assert zone.contains(location) is True


def test_contains_true_for_boundary_point() -> None:
    # Build a square whose corner sits exactly on the single WGS84->UTM
    # projection of this location (matching what contains() does internally
    # — no WGS84<->UTM round trip, which would introduce sub-millimetre
    # floating point noise right at the boundary).
    from pyproj import Transformer

    wgs_to_utm = Transformer.from_crs("EPSG:4326", "EPSG:25830", always_xy=True)
    location = GeoLocation(lat=40.4168, lng=-3.7038)
    bx, by = wgs_to_utm.transform(location.lng, location.lat)

    boundary_square = Polygon([(bx, by), (bx + 20, by), (bx + 20, by + 20), (bx, by + 20)])
    zone = _make_ser_zone(geometry=boundary_square)

    assert zone.contains(location) is True


def test_contains_false_for_exterior_point() -> None:
    zone = _make_ser_zone()
    # Far outside Madrid entirely.
    location = GeoLocation(lat=41.0, lng=-4.5)
    assert zone.contains(location) is False


def _location_at_utm_offset(offset_m: float) -> GeoLocation:
    """
    Build a GeoLocation whose UTM projection sits offset_m metres outside
    _SQUARE's right edge (x = _CENTRE_UTM[0] + 10.0), at the edge's
    mid-point in y. Round-trips through UTM->WGS84->UTM (matching the
    pattern used in test_contains_true_for_boundary_point and the
    infrastructure integration tests) so the distance is exact — no
    sub-millimetre floating point noise from an independently-chosen WGS84
    coordinate.
    """
    from pyproj import Transformer

    utm_to_wgs84 = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)
    x = _CENTRE_UTM[0] + 10.0 + offset_m
    y = _CENTRE_UTM[1]
    lng, lat = utm_to_wgs84.transform(x, y)
    return GeoLocation(lat=lat, lng=lng)


def test_contains_default_tolerance_returns_false_for_point_just_outside() -> None:
    """
    Regression guard: omitting tolerance_m (defaults to 0.0) must preserve
    the exact old zero-tolerance boundary-inclusive behavior — a point 1m
    outside the polygon is still rejected.
    """
    zone = _make_ser_zone()
    location = _location_at_utm_offset(1.0)
    assert zone.contains(location) is False


def test_contains_true_for_point_outside_within_tolerance() -> None:
    """A point 0.5m outside the boundary is contained when tolerance_m=1.0."""
    zone = _make_ser_zone()
    location = _location_at_utm_offset(0.5)
    assert zone.contains(location, tolerance_m=1.0) is True


def test_contains_false_for_point_outside_tolerance() -> None:
    """A point 2m outside the boundary is not contained when tolerance_m=1.0."""
    zone = _make_ser_zone()
    location = _location_at_utm_offset(2.0)
    assert zone.contains(location, tolerance_m=1.0) is False
