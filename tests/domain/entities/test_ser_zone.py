"""Unit tests for SerZone entity."""
import pytest

from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.value_objects.location import GeoLocation


def _make_ser_zone(**kwargs) -> SerZone:
    defaults = dict(
        street_name="Calle Mayor",
        zone_type="Azul",
        spot_count=15,
        location=GeoLocation(lat=40.4168, lng=-3.7038),
    )
    defaults.update(kwargs)
    return SerZone(**defaults)


def test_ser_zone_construction_with_new_fields() -> None:
    zone = _make_ser_zone()

    assert zone.street_name == "Calle Mayor"
    assert zone.zone_type == "Azul"
    assert zone.spot_count == 15
    assert zone.location.lat == pytest.approx(40.4168)
    assert zone.location.lng == pytest.approx(-3.7038)


def test_ser_zone_spot_count_minus_one_for_unknown() -> None:
    zone = _make_ser_zone(spot_count=-1)
    assert zone.spot_count == -1


def test_ser_zone_is_immutable() -> None:
    zone = _make_ser_zone()
    with pytest.raises((AttributeError, TypeError)):
        zone.zone_type = "Verde"  # type: ignore[misc]


def test_ser_zone_no_zone_code_attribute() -> None:
    zone = _make_ser_zone()
    assert not hasattr(zone, "zone_code"), "zone_code must not exist on SerZone"


def test_ser_zone_no_zone_label_attribute() -> None:
    zone = _make_ser_zone()
    assert not hasattr(zone, "zone_label"), "zone_label must not exist on SerZone"
