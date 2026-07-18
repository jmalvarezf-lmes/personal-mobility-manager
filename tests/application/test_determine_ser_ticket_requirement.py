"""Unit tests for DetermineSerTicketRequirement use case."""

from shapely.geometry import Polygon

from mobility_manager.application.use_cases.determine_ser_ticket_requirement import (
    DetermineSerTicketRequirement,
)
from mobility_manager.domain.entities.ser_zone import SerZone

_SQUARE = Polygon([(440584, 4474459), (440604, 4474459), (440604, 4474479), (440584, 4474479)])


class _FakeSerEnforcementSchedule:
    """Minimal fake enforcement schedule returning a fixed answer, mechanical fallout fix (see task 6.1/6.2)."""

    def __init__(self, active: bool) -> None:
        self._active = active
        self.calls: list[str] = []

    def is_active_now(self, city_code: str) -> bool:
        self.calls.append(city_code)
        return self._active


def _make_ser_zone() -> SerZone:
    return SerZone(
        city_code="madrid",
        zone_number="163",
        zone_type="Azul",
        district="CENTRO",
        spot_count=15,
        geometry=_SQUARE,
    )


def test_execute_returns_true_when_zone_is_not_none_and_enforcement_active() -> None:
    use_case = DetermineSerTicketRequirement(enforcement_schedule=_FakeSerEnforcementSchedule(active=True))

    assert use_case.execute(_make_ser_zone()) is True


def test_execute_returns_false_when_zone_is_not_none_and_enforcement_inactive() -> None:
    """
    execute() must return exactly the mock's answer — verified for both the
    True and False cases, since a use case that always returned True
    regardless of the dependency's answer would previously have passed if
    only the True case were tested.
    """
    use_case = DetermineSerTicketRequirement(enforcement_schedule=_FakeSerEnforcementSchedule(active=False))

    assert use_case.execute(_make_ser_zone()) is False


def test_execute_returns_false_when_zone_is_none() -> None:
    use_case = DetermineSerTicketRequirement(enforcement_schedule=_FakeSerEnforcementSchedule(active=True))

    assert use_case.execute(None) is False


def test_execute_does_not_consult_dependency_when_zone_is_none() -> None:
    """zone=None must short-circuit without calling the injected dependency at all."""
    fake_schedule = _FakeSerEnforcementSchedule(active=True)
    use_case = DetermineSerTicketRequirement(enforcement_schedule=fake_schedule)

    use_case.execute(None)

    assert fake_schedule.calls == []


def test_execute_delegates_to_dependency_with_zone_city_code_when_zone_present() -> None:
    """When zone is not None, the dependency must be called with zone.city_code."""
    fake_schedule = _FakeSerEnforcementSchedule(active=True)
    use_case = DetermineSerTicketRequirement(enforcement_schedule=fake_schedule)

    use_case.execute(_make_ser_zone())

    assert fake_schedule.calls == ["madrid"]
