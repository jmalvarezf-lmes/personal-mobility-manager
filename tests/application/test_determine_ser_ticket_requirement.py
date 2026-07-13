"""Unit tests for DetermineSerTicketRequirement use case."""

from shapely.geometry import Polygon

from mobility_manager.application.use_cases.determine_ser_ticket_requirement import (
    DetermineSerTicketRequirement,
)
from mobility_manager.domain.entities.ser_zone import SerZone

_SQUARE = Polygon([(440584, 4474459), (440604, 4474459), (440604, 4474479), (440584, 4474479)])


def _make_ser_zone() -> SerZone:
    return SerZone(
        zone_number="163",
        zone_type="Azul",
        district="CENTRO",
        spot_count=15,
        geometry=_SQUARE,
    )


def test_execute_returns_true_when_zone_is_not_none() -> None:
    use_case = DetermineSerTicketRequirement()

    assert use_case.execute(_make_ser_zone()) is True


def test_execute_returns_false_when_zone_is_none() -> None:
    use_case = DetermineSerTicketRequirement()

    assert use_case.execute(None) is False
