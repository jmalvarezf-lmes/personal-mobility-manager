"""
Unit tests for EvaluateSerTicketRequirementState.

Covers every transition scenario and deactivation reason from the
ser-ticket-requirement-state spec.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from mobility_manager.application.use_cases.evaluate_ser_ticket_requirement_state import (
    EvaluateSerTicketRequirementState,
)
from mobility_manager.application.use_cases.ser_zone_recheck_gate import (
    SerZoneRecheckDecision,
)
from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.entities.vehicle_ser_requirement_state import (
    VehicleSerRequirementState,
)
from mobility_manager.domain.events.ser_ticket_requirement_activated import (
    SerTicketRequirementActivated,
)
from mobility_manager.domain.events.ser_ticket_requirement_deactivated import (
    SerTicketRequirementDeactivated,
)
from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)
from mobility_manager.domain.value_objects.location import GeoLocation
from mobility_manager.domain.value_objects.ser_ticket_requirement_deactivation_reason import (
    SerTicketRequirementDeactivationReason,
)

_LAT, _LNG = 40.4258, -3.7038
_CITY_CODE = "madrid"
_ZONE_NUMBER = "163"


class FakeSerZoneRecheckGate:
    def __init__(self, decision: SerZoneRecheckDecision | None = None) -> None:
        self.decision = decision if decision is not None else SerZoneRecheckDecision(should_check=True, zone=None)
        self.calls: list[tuple[VehicleLocationUpdated, float]] = []

    def evaluate(self, event: VehicleLocationUpdated, movement_floor_meters: float) -> SerZoneRecheckDecision:
        self.calls.append((event, movement_floor_meters))
        return self.decision

    def _zone_for(self, lat: float, lng: float) -> SerZone | None:
        return self.decision.zone


class FakeFindContainingSerZone:
    def __init__(self, zone: SerZone | None = None) -> None:
        self.zone = zone

    def execute(self, location: GeoLocation) -> SerZone | None:
        return self.zone


class FakeDetermineSerTicketRequirement:
    def __init__(self, required: bool = False) -> None:
        self.required = required
        self.calls: list[tuple[SerZone | None, UUID]] = []

    def execute(self, zone: SerZone | None, vehicle_id: UUID, at: datetime) -> bool:
        self.calls.append((zone, vehicle_id))
        return self.required


class FakeParkingTicketRepository:
    def __init__(self, active_tickets: list[object] | None = None) -> None:
        self._active_tickets = active_tickets or []

    def find_all_active_for_vehicle(self, vehicle_id: UUID, at: datetime) -> list[object]:
        return self._active_tickets


class FakeEventPublisher:
    def __init__(self) -> None:
        self.events: list[object] = []

    def publish(self, event: object) -> None:
        self.events.append(event)


def _make_zone(city_code: str = _CITY_CODE, zone_number: str = _ZONE_NUMBER) -> SerZone:
    from shapely.geometry import Polygon

    return SerZone(
        city_code=city_code,
        zone_number=zone_number,
        zone_type="Azul",
        district="CENTRO",
        spot_count=15,
        geometry=Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
    )


def _make_event(vehicle_id: UUID, lat: float = _LAT, lng: float = _LNG, now: datetime | None = None) -> VehicleLocationUpdated:
    return VehicleLocationUpdated(
        vehicle_id=vehicle_id,
        latitude=lat,
        longitude=lng,
        recorded_at=now or datetime.now(UTC),
        received_at=now or datetime.now(UTC),
        source="pull",
    )


def _make_state(
    vehicle_id: UUID,
    is_required: bool = False,
    city_code: str | None = None,
    zone_number: str | None = None,
    activated_at: datetime | None = None,
) -> VehicleSerRequirementState:
    return VehicleSerRequirementState(
        vehicle_id=vehicle_id,
        city_code=city_code,
        zone_number=zone_number,
        is_required=is_required,
        activated_at=activated_at,
        last_evaluated_at=datetime.now(UTC),
    )


class _Fixture:
    def __init__(self) -> None:
        self.zone = _make_zone()
        self.gate = FakeSerZoneRecheckGate(SerZoneRecheckDecision(should_check=True, zone=self.zone))
        self.find_containing = FakeFindContainingSerZone(self.zone)
        self.determine = FakeDetermineSerTicketRequirement(required=False)
        self.ticket_repo = FakeParkingTicketRepository()
        self.event_publisher = FakeEventPublisher()
        self.movement_floor = 10.0

    def build(self) -> EvaluateSerTicketRequirementState:
        return EvaluateSerTicketRequirementState(
            ser_zone_recheck_gate=self.gate,  # type: ignore[arg-type]
            find_containing_ser_zone=self.find_containing,  # type: ignore[arg-type]
            determine_ser_ticket_requirement=self.determine,  # type: ignore[arg-type]
            ticket_repo=self.ticket_repo,  # type: ignore[arg-type]
            event_publisher=self.event_publisher,  # type: ignore[arg-type]
            movement_floor_meters=self.movement_floor,
        )


def test_inactive_to_active_transition() -> None:
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.determine.required = True
    use_case = fx.build()

    state = _make_state(vehicle_id, is_required=False)
    new_state = use_case.execute(_make_event(vehicle_id, now=now), state)

    assert new_state.is_required is True
    assert new_state.city_code == _CITY_CODE
    assert new_state.zone_number == _ZONE_NUMBER
    assert new_state.activated_at == now
    assert len(fx.event_publisher.events) == 1
    event = fx.event_publisher.events[0]
    assert isinstance(event, SerTicketRequirementActivated)
    assert event.vehicle_id == vehicle_id
    assert event.city_code == _CITY_CODE
    assert event.zone_number == _ZONE_NUMBER


def test_active_to_inactive_transition_left_zone() -> None:
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.determine.required = False
    fx.find_containing.zone = None
    use_case = fx.build()

    state = _make_state(vehicle_id, is_required=True, city_code=_CITY_CODE, zone_number=_ZONE_NUMBER)
    new_state = use_case.execute(_make_event(vehicle_id, now=now), state)

    assert new_state.is_required is False
    assert new_state.city_code is None
    assert new_state.zone_number is None
    assert len(fx.event_publisher.events) == 1
    event = fx.event_publisher.events[0]
    assert isinstance(event, SerTicketRequirementDeactivated)
    assert event.reason == SerTicketRequirementDeactivationReason.LEFT_ZONE


def test_active_to_inactive_transition_ticket_active() -> None:
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.determine.required = False

    class _Ticket:
        def __init__(self) -> None:
            self.city_code = _CITY_CODE
            self.zone_number = _ZONE_NUMBER

    fx.ticket_repo = FakeParkingTicketRepository(active_tickets=[_Ticket()])
    use_case = fx.build()

    state = _make_state(vehicle_id, is_required=True, city_code=_CITY_CODE, zone_number=_ZONE_NUMBER)
    new_state = use_case.execute(_make_event(vehicle_id, now=now), state)

    assert new_state.is_required is False
    assert len(fx.event_publisher.events) == 1
    event = fx.event_publisher.events[0]
    assert isinstance(event, SerTicketRequirementDeactivated)
    assert event.reason == SerTicketRequirementDeactivationReason.TICKET_ACTIVE


def test_active_to_active_does_not_publish_event() -> None:
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.determine.required = True
    use_case = fx.build()

    state = _make_state(vehicle_id, is_required=True, city_code=_CITY_CODE, zone_number=_ZONE_NUMBER)
    new_state = use_case.execute(_make_event(vehicle_id, now=now), state)

    assert new_state.is_required is True
    assert fx.event_publisher.events == []


def test_inactive_to_inactive_does_not_publish_event() -> None:
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.determine.required = False
    use_case = fx.build()

    state = _make_state(vehicle_id, is_required=False)
    new_state = use_case.execute(_make_event(vehicle_id, now=now), state)

    assert new_state.is_required is False
    assert fx.event_publisher.events == []


def test_inactive_state_uses_gate_and_skips_when_should_check_false() -> None:
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.gate.decision = SerZoneRecheckDecision(should_check=False, zone=None)
    use_case = fx.build()

    state = _make_state(vehicle_id, is_required=False)
    new_state = use_case.execute(_make_event(vehicle_id, now=now), state)

    assert new_state.is_required is False
    assert fx.determine.calls == []
    assert fx.event_publisher.events == []
    assert len(fx.gate.calls) == 1
    _event, floor = fx.gate.calls[0]
    assert floor == 10.0


def test_active_state_bypasses_gate_and_always_evaluates() -> None:
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.gate.calls.clear()
    fx.determine.required = True
    use_case = fx.build()

    state = _make_state(vehicle_id, is_required=True, city_code=_CITY_CODE, zone_number=_ZONE_NUMBER)
    use_case.execute(_make_event(vehicle_id, now=now), state)

    assert fx.gate.calls == []
    assert len(fx.determine.calls) == 1


def test_no_state_defaults_to_inactive() -> None:
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.determine.required = True
    use_case = fx.build()

    new_state = use_case.execute(_make_event(vehicle_id, now=now), None)

    assert new_state.is_required is True
    assert len(fx.event_publisher.events) == 1
    assert isinstance(fx.event_publisher.events[0], SerTicketRequirementActivated)
