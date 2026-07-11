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
