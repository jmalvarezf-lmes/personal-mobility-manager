"""
Unit tests for CitySerExemptionZoneRule.

Covers the `ser-exemption-zone-rule` spec's "Madrid green zone is eligible",
"Madrid non-green zone is not eligible", and "Non-Madrid cities are always
eligible" scenarios.
"""

from shapely.geometry import Polygon

from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.infrastructure.parking_services.ser_exemption_zone_rules import (
    CitySerExemptionZoneRule,
)

_SQUARE = Polygon([(440584, 4474459), (440604, 4474459), (440604, 4474479), (440584, 4474479)])


def _make_ser_zone(city_code: str, zone_type: str) -> SerZone:
    return SerZone(
        city_code=city_code,
        zone_number="163",
        zone_type=zone_type,
        district="CENTRO",
        spot_count=15,
        geometry=_SQUARE,
    )


def test_madrid_green_zone_is_eligible() -> None:
    rule = CitySerExemptionZoneRule()

    assert rule.is_zone_eligible(_make_ser_zone(city_code="madrid", zone_type="Verde")) is True


def test_madrid_non_green_zone_is_not_eligible() -> None:
    rule = CitySerExemptionZoneRule()

    assert rule.is_zone_eligible(_make_ser_zone(city_code="madrid", zone_type="Azul")) is False


def test_non_madrid_cities_are_always_eligible() -> None:
    rule = CitySerExemptionZoneRule()

    assert rule.is_zone_eligible(_make_ser_zone(city_code="barcelona", zone_type="Azul")) is True
