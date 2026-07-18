"""Unit tests for the ZoneArea domain value object."""

import dataclasses

import pytest
from shapely.geometry import Polygon

from mobility_manager.domain.value_objects.zone_area import ZoneArea

_POLYGON = Polygon([(440000, 4474000), (440100, 4474000), (440100, 4474100), (440000, 4474100)])


def _make_zone_area(**kwargs) -> ZoneArea:
    defaults = {
        "city_code": "madrid",
        "zone_number": "163",
        "neighbourhood": "Sol",
        "geometry": _POLYGON,
    }
    defaults.update(kwargs)
    return ZoneArea(**defaults)


def test_zone_area_is_immutable() -> None:
    zone_area = _make_zone_area()
    with pytest.raises(dataclasses.FrozenInstanceError):
        zone_area.neighbourhood = "Palacio"  # type: ignore[misc]


def test_zone_area_has_no_contains_method() -> None:
    zone_area = _make_zone_area()
    assert not hasattr(zone_area, "contains")


def test_zone_area_fields() -> None:
    zone_area = _make_zone_area()
    assert zone_area.zone_number == "163"
    assert zone_area.neighbourhood == "Sol"
    assert zone_area.geometry == _POLYGON


def test_zone_area_carries_and_exposes_city_code() -> None:
    """ZoneArea must carry city_code to disambiguate zone_number values that
    may collide across cities (see add-ser-enforcement-calendar design.md D5)."""
    zone_area = _make_zone_area(city_code="madrid")
    assert zone_area.city_code == "madrid"

    other_city_zone_area = _make_zone_area(city_code="barcelona")
    assert other_city_zone_area.city_code == "barcelona"


def test_two_cities_sharing_zone_number_are_distinguishable_by_city_code() -> None:
    madrid_area = _make_zone_area(city_code="madrid", zone_number="100")
    barcelona_area = _make_zone_area(city_code="barcelona", zone_number="100")

    assert madrid_area.zone_number == barcelona_area.zone_number
    assert madrid_area.city_code != barcelona_area.city_code
