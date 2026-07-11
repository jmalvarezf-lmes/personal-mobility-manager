"""Unit tests for FindNearestSerZone use case."""

from unittest.mock import MagicMock

import pytest
from shapely.geometry import Polygon

from mobility_manager.application.use_cases.find_nearest_ser_zone import (
    FindNearestSerZone,
)
from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.exceptions import SerZoneNotFoundError
from mobility_manager.domain.value_objects.location import GeoLocation

_SQUARE = Polygon([(440584, 4474459), (440604, 4474459), (440604, 4474479), (440584, 4474479)])


def _make_ser_zone() -> SerZone:
    return SerZone(
        zone_number="163",
        zone_type="Azul",
        district="CENTRO",
        spot_count=15,
        geometry=_SQUARE,
    )


def test_execute_returns_ser_zone_when_found() -> None:
    repo = MagicMock()
    repo.find_nearest.return_value = _make_ser_zone()

    use_case = FindNearestSerZone(repo=repo)
    location = GeoLocation(lat=40.4168, lng=-3.7038)
    result = use_case.execute(location)

    assert result.zone_number == "163"
    assert result.zone_type == "Azul"
    assert result.district == "CENTRO"
    assert result.spot_count == 15
    repo.find_nearest.assert_called_once_with(location)


def test_execute_raises_when_not_found() -> None:
    repo = MagicMock()
    repo.find_nearest.return_value = None

    use_case = FindNearestSerZone(repo=repo)
    location = GeoLocation(lat=40.4168, lng=-3.7038)

    with pytest.raises(SerZoneNotFoundError):
        use_case.execute(location)
