"""Unit tests for GeoLocation value object."""
import pytest

from mobility_manager.domain.value_objects.location import GeoLocation


def test_valid_geolocation() -> None:
    loc = GeoLocation(lat=40.4168, lng=-3.7038)
    assert loc.lat == 40.4168
    assert loc.lng == -3.7038


def test_geolocation_is_frozen() -> None:
    loc = GeoLocation(lat=40.0, lng=-3.0)
    with pytest.raises(Exception):  # FrozenInstanceError
        loc.lat = 0.0  # type: ignore[misc]


def test_lat_below_minus_90_raises() -> None:
    with pytest.raises(ValueError, match="Latitude"):
        GeoLocation(lat=-90.1, lng=0.0)


def test_lat_above_90_raises() -> None:
    with pytest.raises(ValueError, match="Latitude"):
        GeoLocation(lat=90.1, lng=0.0)


def test_lat_exactly_minus_90_is_valid() -> None:
    loc = GeoLocation(lat=-90.0, lng=0.0)
    assert loc.lat == -90.0


def test_lat_exactly_90_is_valid() -> None:
    loc = GeoLocation(lat=90.0, lng=0.0)
    assert loc.lat == 90.0


def test_lng_below_minus_180_raises() -> None:
    with pytest.raises(ValueError, match="Longitude"):
        GeoLocation(lat=0.0, lng=-180.1)


def test_lng_above_180_raises() -> None:
    with pytest.raises(ValueError, match="Longitude"):
        GeoLocation(lat=0.0, lng=180.1)


def test_lng_exactly_minus_180_is_valid() -> None:
    loc = GeoLocation(lat=0.0, lng=-180.0)
    assert loc.lng == -180.0


def test_lng_exactly_180_is_valid() -> None:
    loc = GeoLocation(lat=0.0, lng=180.0)
    assert loc.lng == 180.0
