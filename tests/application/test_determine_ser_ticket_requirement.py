"""Unit tests for DetermineSerTicketRequirement use case."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from shapely.geometry import Polygon

from mobility_manager.application.use_cases.determine_ser_ticket_requirement import (
    DetermineSerTicketRequirement,
)
from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.entities.vehicle_ser_parking_exemption import (
    VehicleSerParkingExemption,
)

_SQUARE = Polygon([(440584, 4474459), (440604, 4474459), (440604, 4474479), (440584, 4474479)])


class _FakeSerEnforcementSchedule:
    """Minimal fake enforcement schedule returning a fixed answer, mechanical fallout fix (see task 6.1/6.2)."""

    def __init__(self, active: bool) -> None:
        self._active = active
        self.calls: list[str] = []

    def is_active_now(self, city_code: str) -> bool:
        self.calls.append(city_code)
        return self._active


class _FakeVehicleSerParkingExemptionRepository:
    """Minimal fake exemption repository returning a fixed answer."""

    def __init__(self, exemption: VehicleSerParkingExemption | None = None) -> None:
        self._exemption = exemption
        self.calls: list[UUID] = []

    def find_by_vehicle_id(self, vehicle_id: UUID) -> VehicleSerParkingExemption | None:
        self.calls.append(vehicle_id)
        return self._exemption

    def upsert(self, vehicle_id, city_code, zone_number):  # pragma: no cover - not exercised
        raise NotImplementedError

    def delete(self, vehicle_id):  # pragma: no cover - not exercised
        raise NotImplementedError


def _make_ser_zone(zone_number: str = "163") -> SerZone:
    return SerZone(
        city_code="madrid",
        zone_number=zone_number,
        zone_type="Azul",
        district="CENTRO",
        spot_count=15,
        geometry=_SQUARE,
    )


def _make_exemption(vehicle_id: UUID, city_code: str = "madrid", zone_number: str = "163") -> VehicleSerParkingExemption:
    return VehicleSerParkingExemption(
        vehicle_id=vehicle_id,
        city_code=city_code,
        zone_number=zone_number,
        updated_at=datetime.now(UTC),
    )


def test_execute_returns_true_when_zone_is_not_none_and_enforcement_active_no_exemption() -> None:
    vehicle_id = uuid4()
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=_FakeSerEnforcementSchedule(active=True),
        exemption_repo=_FakeVehicleSerParkingExemptionRepository(exemption=None),
    )

    assert use_case.execute(_make_ser_zone(), vehicle_id) is True


def test_execute_returns_false_when_zone_is_not_none_and_enforcement_inactive() -> None:
    """
    execute() must return exactly the mock's answer — verified for both the
    True and False cases, since a use case that always returned True
    regardless of the dependency's answer would previously have passed if
    only the True case were tested.
    """
    vehicle_id = uuid4()
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=_FakeSerEnforcementSchedule(active=False),
        exemption_repo=_FakeVehicleSerParkingExemptionRepository(exemption=None),
    )

    assert use_case.execute(_make_ser_zone(), vehicle_id) is False


def test_execute_returns_false_when_zone_is_none() -> None:
    vehicle_id = uuid4()
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=_FakeSerEnforcementSchedule(active=True),
        exemption_repo=_FakeVehicleSerParkingExemptionRepository(exemption=None),
    )

    assert use_case.execute(None, vehicle_id) is False


def test_execute_does_not_consult_dependencies_when_zone_is_none() -> None:
    """zone=None must short-circuit without calling either injected dependency."""
    vehicle_id = uuid4()
    fake_schedule = _FakeSerEnforcementSchedule(active=True)
    fake_exemption_repo = _FakeVehicleSerParkingExemptionRepository(exemption=None)
    use_case = DetermineSerTicketRequirement(enforcement_schedule=fake_schedule, exemption_repo=fake_exemption_repo)

    use_case.execute(None, vehicle_id)

    assert fake_schedule.calls == []
    assert fake_exemption_repo.calls == []


def test_execute_does_not_consult_exemption_repo_when_enforcement_inactive() -> None:
    """Enforcement-inactive must short-circuit before the exemption repository is consulted."""
    vehicle_id = uuid4()
    fake_exemption_repo = _FakeVehicleSerParkingExemptionRepository(exemption=None)
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=_FakeSerEnforcementSchedule(active=False),
        exemption_repo=fake_exemption_repo,
    )

    use_case.execute(_make_ser_zone(), vehicle_id)

    assert fake_exemption_repo.calls == []


def test_execute_delegates_to_enforcement_schedule_with_zone_city_code_when_zone_present() -> None:
    """When zone is not None, the enforcement-schedule dependency must be called with zone.city_code."""
    vehicle_id = uuid4()
    fake_schedule = _FakeSerEnforcementSchedule(active=True)
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=fake_schedule,
        exemption_repo=_FakeVehicleSerParkingExemptionRepository(exemption=None),
    )

    use_case.execute(_make_ser_zone(), vehicle_id)

    assert fake_schedule.calls == ["madrid"]


def test_execute_returns_false_when_vehicle_has_matching_exemption() -> None:
    vehicle_id = uuid4()
    exemption = _make_exemption(vehicle_id, city_code="madrid", zone_number="163")
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=_FakeSerEnforcementSchedule(active=True),
        exemption_repo=_FakeVehicleSerParkingExemptionRepository(exemption=exemption),
    )

    assert use_case.execute(_make_ser_zone(zone_number="163"), vehicle_id) is False


def test_execute_returns_true_when_vehicle_exemption_is_for_a_different_zone() -> None:
    vehicle_id = uuid4()
    exemption = _make_exemption(vehicle_id, city_code="madrid", zone_number="200")
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=_FakeSerEnforcementSchedule(active=True),
        exemption_repo=_FakeVehicleSerParkingExemptionRepository(exemption=exemption),
    )

    assert use_case.execute(_make_ser_zone(zone_number="163"), vehicle_id) is True


def test_execute_looks_up_exemption_by_vehicle_id() -> None:
    vehicle_id = uuid4()
    fake_exemption_repo = _FakeVehicleSerParkingExemptionRepository(exemption=None)
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=_FakeSerEnforcementSchedule(active=True),
        exemption_repo=fake_exemption_repo,
    )

    use_case.execute(_make_ser_zone(), vehicle_id)

    assert fake_exemption_repo.calls == [vehicle_id]
