"""Unit tests for FindContainingSerZone use case."""

from unittest.mock import MagicMock

from shapely.geometry import Polygon

from mobility_manager.application.use_cases.find_containing_ser_zone import (
    FindContainingSerZone,
)
from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.value_objects.location import GeoLocation

_SQUARE = Polygon([(440584, 4474459), (440604, 4474459), (440604, 4474479), (440584, 4474479)])


def _make_ser_zone() -> SerZone:
    return SerZone(
        city_code="madrid",
        zone_number="163",
        zone_type="Azul",
        district="CENTRO",
        spot_count=15,
        geometry=_SQUARE,
    )


def test_execute_returns_zone_when_inside() -> None:
    repo = MagicMock()
    repo.find_containing.return_value = _make_ser_zone()

    use_case = FindContainingSerZone(repo=repo)
    location = GeoLocation(lat=40.4168, lng=-3.7038)
    result = use_case.execute(location)

    assert result is not None
    assert result.zone_number == "163"
    repo.find_containing.assert_called_once_with(location)


def test_execute_returns_none_without_raising_when_outside_all_zones() -> None:
    repo = MagicMock()
    repo.find_containing.return_value = None

    use_case = FindContainingSerZone(repo=repo)
    location = GeoLocation(lat=40.4168, lng=-3.7038)
    result = use_case.execute(location)

    assert result is None


def test_execute_never_consults_zone_area_frontier_data() -> None:
    """
    Containment logic must depend only on ser_zones precise geometry, never
    on ser_zone_areas frontier data (ser-zone-query spec: "Containment logic
    is unaffected by frontier data").
    """
    repo = MagicMock()
    repo.find_containing.return_value = _make_ser_zone()

    use_case = FindContainingSerZone(repo=repo)
    location = GeoLocation(lat=40.4168, lng=-3.7038)
    use_case.execute(location)

    repo.get_zone_area.assert_not_called()
    repo.list_zone_areas.assert_not_called()
