"""Unit tests for FindNearestSerZone use case."""
from unittest.mock import MagicMock

import pytest

from mobility_manager.application.use_cases.find_nearest_ser_zone import (
    FindNearestSerZone,
)
from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.exceptions import SerZoneNotFoundError
from mobility_manager.domain.value_objects.location import GeoLocation


def _make_ser_zone() -> SerZone:
    return SerZone(
        street_name="Calle Mayor",
        zone_type="Azul",
        spot_count=15,
        location=GeoLocation(lat=40.4168, lng=-3.7038),
    )


def test_execute_returns_ser_zone_when_found() -> None:
    repo = MagicMock()
    repo.find_nearest.return_value = _make_ser_zone()

    use_case = FindNearestSerZone(repo=repo)
    location = GeoLocation(lat=40.4168, lng=-3.7038)
    result = use_case.execute(location)

    assert result.street_name == "Calle Mayor"
    assert result.zone_type == "Azul"
    assert result.spot_count == 15
    repo.find_nearest.assert_called_once_with(location)


def test_execute_raises_when_not_found() -> None:
    repo = MagicMock()
    repo.find_nearest.return_value = None

    use_case = FindNearestSerZone(repo=repo)
    location = GeoLocation(lat=40.4168, lng=-3.7038)

    with pytest.raises(SerZoneNotFoundError):
        use_case.execute(location)
