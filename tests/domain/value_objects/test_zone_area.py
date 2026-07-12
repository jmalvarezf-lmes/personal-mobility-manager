"""Unit tests for the ZoneArea domain value object."""

import dataclasses

import pytest
from shapely.geometry import Polygon

from mobility_manager.domain.value_objects.zone_area import ZoneArea

_POLYGON = Polygon([(440000, 4474000), (440100, 4474000), (440100, 4474100), (440000, 4474100)])


def _make_zone_area(**kwargs) -> ZoneArea:
    defaults = {
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
