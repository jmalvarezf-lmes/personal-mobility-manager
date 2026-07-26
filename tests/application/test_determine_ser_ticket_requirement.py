"""Unit tests for DetermineSerTicketRequirement use case."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from shapely.geometry import Polygon

from mobility_manager.application.use_cases.determine_ser_ticket_requirement import (
    DetermineSerTicketRequirement,
)
from mobility_manager.domain.entities.parking_ticket import ParkingTicket
from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.entities.vehicle_ser_parking_exemption import (
    VehicleSerParkingExemption,
)

_SQUARE = Polygon([(440584, 4474459), (440604, 4474459), (440604, 4474479), (440584, 4474479)])
_NOW = datetime.now(UTC)


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


class _FakeSerExemptionZoneRule:
    """Minimal fake exemption zone rule returning a fixed answer."""

    def __init__(self, eligible: bool = True) -> None:
        self._eligible = eligible
        self.calls: list[SerZone] = []

    def is_zone_eligible(self, zone: SerZone) -> bool:
        self.calls.append(zone)
        return self._eligible


class _FakeParkingTicketRepository:
    """Minimal fake ParkingTicket repository returning a fixed answer."""

    def __init__(self, active_ticket: ParkingTicket | None = None) -> None:
        self._active_ticket = active_ticket
        self.calls: list[tuple[UUID, datetime]] = []

    def find_active_for_vehicle(self, vehicle_id: UUID, at: datetime) -> ParkingTicket | None:
        self.calls.append((vehicle_id, at))
        return self._active_ticket


def _make_ser_zone(zone_number: str = "163", zone_type: str = "Azul") -> SerZone:
    return SerZone(
        city_code="madrid",
        zone_number=zone_number,
        zone_type=zone_type,
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


def _make_ticket(vehicle_id: UUID) -> ParkingTicket:
    return ParkingTicket(
        id=uuid4(),
        vehicle_id=vehicle_id,
        user_id=uuid4(),
        provider="elparking",
        duration_minutes=60,
        provider_reference="ref-123",
        cost=1.5,
        end_date=_NOW,
        created_at=_NOW,
    )


def test_execute_returns_true_when_zone_is_not_none_and_enforcement_active_no_exemption() -> None:
    vehicle_id = uuid4()
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=_FakeSerEnforcementSchedule(active=True),
        exemption_repo=_FakeVehicleSerParkingExemptionRepository(exemption=None),
        exemption_zone_rule=_FakeSerExemptionZoneRule(),
        ticket_repo=_FakeParkingTicketRepository(active_ticket=None),
    )

    assert use_case.execute(_make_ser_zone(), vehicle_id, at=_NOW) is True


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
        exemption_zone_rule=_FakeSerExemptionZoneRule(),
        ticket_repo=_FakeParkingTicketRepository(active_ticket=None),
    )

    assert use_case.execute(_make_ser_zone(), vehicle_id, at=_NOW) is False


def test_execute_returns_false_when_zone_is_none() -> None:
    vehicle_id = uuid4()
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=_FakeSerEnforcementSchedule(active=True),
        exemption_repo=_FakeVehicleSerParkingExemptionRepository(exemption=None),
        exemption_zone_rule=_FakeSerExemptionZoneRule(),
        ticket_repo=_FakeParkingTicketRepository(active_ticket=None),
    )

    assert use_case.execute(None, vehicle_id, at=_NOW) is False


def test_execute_does_not_consult_dependencies_when_zone_is_none() -> None:
    """zone=None must short-circuit without calling any injected dependency."""
    vehicle_id = uuid4()
    fake_schedule = _FakeSerEnforcementSchedule(active=True)
    fake_exemption_repo = _FakeVehicleSerParkingExemptionRepository(exemption=None)
    fake_zone_rule = _FakeSerExemptionZoneRule()
    fake_ticket_repo = _FakeParkingTicketRepository(active_ticket=None)
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=fake_schedule,
        exemption_repo=fake_exemption_repo,
        exemption_zone_rule=fake_zone_rule,
        ticket_repo=fake_ticket_repo,
    )

    use_case.execute(None, vehicle_id, at=_NOW)

    assert fake_schedule.calls == []
    assert fake_exemption_repo.calls == []
    assert fake_zone_rule.calls == []
    assert fake_ticket_repo.calls == []


def test_execute_does_not_consult_exemption_repo_when_enforcement_inactive() -> None:
    """Enforcement-inactive must short-circuit before the exemption repository is consulted."""
    vehicle_id = uuid4()
    fake_exemption_repo = _FakeVehicleSerParkingExemptionRepository(exemption=None)
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=_FakeSerEnforcementSchedule(active=False),
        exemption_repo=fake_exemption_repo,
        exemption_zone_rule=_FakeSerExemptionZoneRule(),
        ticket_repo=_FakeParkingTicketRepository(active_ticket=None),
    )

    use_case.execute(_make_ser_zone(), vehicle_id, at=_NOW)

    assert fake_exemption_repo.calls == []


def test_execute_does_not_consult_ticket_repo_when_enforcement_inactive() -> None:
    """Enforcement-inactive must short-circuit before the ticket repository is consulted."""
    vehicle_id = uuid4()
    fake_ticket_repo = _FakeParkingTicketRepository(active_ticket=None)
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=_FakeSerEnforcementSchedule(active=False),
        exemption_repo=_FakeVehicleSerParkingExemptionRepository(exemption=None),
        exemption_zone_rule=_FakeSerExemptionZoneRule(),
        ticket_repo=fake_ticket_repo,
    )

    use_case.execute(_make_ser_zone(), vehicle_id, at=_NOW)

    assert fake_ticket_repo.calls == []


def test_execute_delegates_to_enforcement_schedule_with_zone_city_code_when_zone_present() -> None:
    """When zone is not None, the enforcement-schedule dependency must be called with zone.city_code."""
    vehicle_id = uuid4()
    fake_schedule = _FakeSerEnforcementSchedule(active=True)
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=fake_schedule,
        exemption_repo=_FakeVehicleSerParkingExemptionRepository(exemption=None),
        exemption_zone_rule=_FakeSerExemptionZoneRule(),
        ticket_repo=_FakeParkingTicketRepository(active_ticket=None),
    )

    use_case.execute(_make_ser_zone(), vehicle_id, at=_NOW)

    assert fake_schedule.calls == ["madrid"]


def test_execute_returns_false_when_active_ticket_exists() -> None:
    """An already-active ParkingTicket short-circuits to False (idempotency guard, fix 11.1)."""
    vehicle_id = uuid4()
    fake_ticket_repo = _FakeParkingTicketRepository(active_ticket=_make_ticket(vehicle_id))
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=_FakeSerEnforcementSchedule(active=True),
        exemption_repo=_FakeVehicleSerParkingExemptionRepository(exemption=None),
        exemption_zone_rule=_FakeSerExemptionZoneRule(),
        ticket_repo=fake_ticket_repo,
    )

    assert use_case.execute(_make_ser_zone(), vehicle_id, at=_NOW) is False


def test_execute_does_not_consult_exemption_repo_or_zone_rule_when_active_ticket_exists() -> None:
    vehicle_id = uuid4()
    fake_exemption_repo = _FakeVehicleSerParkingExemptionRepository(exemption=None)
    fake_zone_rule = _FakeSerExemptionZoneRule()
    fake_ticket_repo = _FakeParkingTicketRepository(active_ticket=_make_ticket(vehicle_id))
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=_FakeSerEnforcementSchedule(active=True),
        exemption_repo=fake_exemption_repo,
        exemption_zone_rule=fake_zone_rule,
        ticket_repo=fake_ticket_repo,
    )

    use_case.execute(_make_ser_zone(), vehicle_id, at=_NOW)

    assert fake_exemption_repo.calls == []
    assert fake_zone_rule.calls == []


def test_execute_consults_ticket_repo_with_vehicle_id_and_at() -> None:
    vehicle_id = uuid4()
    fake_ticket_repo = _FakeParkingTicketRepository(active_ticket=None)
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=_FakeSerEnforcementSchedule(active=True),
        exemption_repo=_FakeVehicleSerParkingExemptionRepository(exemption=None),
        exemption_zone_rule=_FakeSerExemptionZoneRule(),
        ticket_repo=fake_ticket_repo,
    )

    use_case.execute(_make_ser_zone(), vehicle_id, at=_NOW)

    assert fake_ticket_repo.calls == [(vehicle_id, _NOW)]


def test_execute_proceeds_as_before_when_no_active_ticket() -> None:
    """No active ticket must not change the pre-existing exemption/zone-rule behavior."""
    vehicle_id = uuid4()
    exemption = _make_exemption(vehicle_id, city_code="madrid", zone_number="163")
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=_FakeSerEnforcementSchedule(active=True),
        exemption_repo=_FakeVehicleSerParkingExemptionRepository(exemption=exemption),
        exemption_zone_rule=_FakeSerExemptionZoneRule(eligible=True),
        ticket_repo=_FakeParkingTicketRepository(active_ticket=None),
    )

    zone = _make_ser_zone(zone_number="163", zone_type="Verde")

    assert use_case.execute(zone, vehicle_id, at=_NOW) is False


def test_execute_returns_false_when_vehicle_has_matching_exemption() -> None:
    """A matching exemption in a green ("Verde") Madrid zone remains exempt."""
    vehicle_id = uuid4()
    exemption = _make_exemption(vehicle_id, city_code="madrid", zone_number="163")
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=_FakeSerEnforcementSchedule(active=True),
        exemption_repo=_FakeVehicleSerParkingExemptionRepository(exemption=exemption),
        exemption_zone_rule=_FakeSerExemptionZoneRule(eligible=True),
        ticket_repo=_FakeParkingTicketRepository(active_ticket=None),
    )

    zone = _make_ser_zone(zone_number="163", zone_type="Verde")

    assert use_case.execute(zone, vehicle_id, at=_NOW) is False


def test_execute_returns_true_when_vehicle_has_matching_exemption_but_zone_rule_rejects_zone() -> None:
    """A matching exemption in a non-green Madrid zone now requires a ticket."""
    vehicle_id = uuid4()
    exemption = _make_exemption(vehicle_id, city_code="madrid", zone_number="163")
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=_FakeSerEnforcementSchedule(active=True),
        exemption_repo=_FakeVehicleSerParkingExemptionRepository(exemption=exemption),
        exemption_zone_rule=_FakeSerExemptionZoneRule(eligible=False),
        ticket_repo=_FakeParkingTicketRepository(active_ticket=None),
    )

    zone = _make_ser_zone(zone_number="163", zone_type="Azul")

    assert use_case.execute(zone, vehicle_id, at=_NOW) is True


def test_execute_returns_true_when_vehicle_exemption_is_for_a_different_zone() -> None:
    vehicle_id = uuid4()
    exemption = _make_exemption(vehicle_id, city_code="madrid", zone_number="200")
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=_FakeSerEnforcementSchedule(active=True),
        exemption_repo=_FakeVehicleSerParkingExemptionRepository(exemption=exemption),
        exemption_zone_rule=_FakeSerExemptionZoneRule(),
        ticket_repo=_FakeParkingTicketRepository(active_ticket=None),
    )

    assert use_case.execute(_make_ser_zone(zone_number="163"), vehicle_id, at=_NOW) is True


def test_execute_does_not_consult_zone_rule_when_exemption_does_not_match() -> None:
    """No matching exemption must short-circuit before the zone rule is consulted."""
    vehicle_id = uuid4()
    exemption = _make_exemption(vehicle_id, city_code="madrid", zone_number="200")
    fake_zone_rule = _FakeSerExemptionZoneRule()
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=_FakeSerEnforcementSchedule(active=True),
        exemption_repo=_FakeVehicleSerParkingExemptionRepository(exemption=exemption),
        exemption_zone_rule=fake_zone_rule,
        ticket_repo=_FakeParkingTicketRepository(active_ticket=None),
    )

    use_case.execute(_make_ser_zone(zone_number="163"), vehicle_id, at=_NOW)

    assert fake_zone_rule.calls == []


def test_execute_looks_up_exemption_by_vehicle_id() -> None:
    vehicle_id = uuid4()
    fake_exemption_repo = _FakeVehicleSerParkingExemptionRepository(exemption=None)
    use_case = DetermineSerTicketRequirement(
        enforcement_schedule=_FakeSerEnforcementSchedule(active=True),
        exemption_repo=fake_exemption_repo,
        exemption_zone_rule=_FakeSerExemptionZoneRule(),
        ticket_repo=_FakeParkingTicketRepository(active_ticket=None),
    )

    use_case.execute(_make_ser_zone(), vehicle_id, at=_NOW)

    assert fake_exemption_repo.calls == [vehicle_id]
