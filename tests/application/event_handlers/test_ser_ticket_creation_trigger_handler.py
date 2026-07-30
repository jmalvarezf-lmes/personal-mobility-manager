"""
Unit tests for SerTicketCreationTriggerHandler.

Covers every scenario in the ser-ticket-auto-creation spec: ticket created
when required (gate signals should_check), no-op when auto_create_ticket is
disabled, SerZoneRecheckGate signalling no check needed, a stationary
vehicle with no active ticket still reaching DetermineSerTicketRequirement,
zone-none short-circuit, missing-vehicle skip, and each mapped failure
reason (mocked ports, no real DB).

The previous-location/distance/zone-comparison logic itself now lives in
SerZoneRecheckGate (see change-ser-ticket-stationary-recheck design.md
D3/D4) and is unit-tested there (test_ser_zone_recheck_gate.py) — this
handler is tested here against a mocked gate, asserting only that its
decision is respected and that `movement_floor_meters` is resolved from
`get_ser_ticket_creation_zone_change_floor_meters()`.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from shapely.geometry import Polygon

from mobility_manager.application.event_handlers.ser_ticket_creation_trigger_handler import (
    SerTicketCreationTriggerHandler,
)
from mobility_manager.application.use_cases.ser_zone_recheck_gate import (
    SerZoneRecheckDecision,
)
from mobility_manager.domain.entities.parking_ticket import ParkingTicket
from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.entities.user_preferences import UserPreferences
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.events.ser_ticket_created import SerTicketCreated
from mobility_manager.domain.events.ser_ticket_creation_failed import (
    SerTicketCreationFailed,
)
from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)
from mobility_manager.domain.exceptions import (
    SerProviderApiError,
    SerProviderSessionNotFoundError,
    SerProviderVehicleNotFoundError,
    SerTicketPersistenceError,
    SerZoneNotFoundError,
)
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.domain.value_objects.location import GeoLocation

_MOVED_LAT, _MOVED_LNG = 40.4258, -3.7038

_SQUARE = Polygon([(440584, 4474459), (440604, 4474459), (440604, 4474479), (440584, 4474479)])


class FakeVehicleRepo:
    def __init__(self) -> None:
        self.vehicles: dict[UUID, Vehicle] = {}

    def add(self, vehicle: Vehicle) -> None:
        self.vehicles[vehicle.id] = vehicle

    def get_by_id(self, vehicle_id: UUID) -> Vehicle | None:
        return self.vehicles.get(vehicle_id)


class FakeUserPreferencesRepo:
    def __init__(self) -> None:
        self.preferences: dict[UUID, UserPreferences] = {}

    def set(self, user_id: UUID, auto_create_ticket: bool, default_ticket_duration_minutes: int = 60) -> None:
        self.preferences[user_id] = UserPreferences(
            user_id=user_id,
            default_ticket_duration_minutes=default_ticket_duration_minutes,
            auto_create_ticket=auto_create_ticket,
            preferred_notification_channel=None,
            notification_language=None,
            timezone=None,
            updated_at=datetime.now(UTC),
        )

    def find_by_user_id(self, user_id: UUID) -> UserPreferences | None:
        return self.preferences.get(user_id)


class FakeUserSerProviderConfigRepo:
    def __init__(self) -> None:
        self.connected: dict[UUID, list[str]] = {}

    def set_connected(self, user_id: UUID, providers: list[str]) -> None:
        self.connected[user_id] = providers

    def list_connected_providers(self, user_id: UUID) -> list[str]:
        return self.connected.get(user_id, [])


class FakeDetermineSerTicketRequirement:
    def __init__(self, required: bool = True) -> None:
        self.required = required
        self.calls: list[tuple[SerZone | None, UUID]] = []

    def execute(self, zone: SerZone | None, vehicle_id: UUID, at=None) -> bool:
        self.calls.append((zone, vehicle_id))
        return self.required


class FakeSerZoneRecheckGate:
    def __init__(self, decision: SerZoneRecheckDecision | None = None) -> None:
        self.decision = decision if decision is not None else SerZoneRecheckDecision(should_check=True, zone=None)
        self.calls: list[tuple[VehicleLocationUpdated, float]] = []

    def evaluate(self, event: VehicleLocationUpdated, movement_floor_meters: float) -> SerZoneRecheckDecision:
        self.calls.append((event, movement_floor_meters))
        return self.decision


class FakeCreateSerTicket:
    def __init__(self, ticket: ParkingTicket | None = None, raises: Exception | None = None) -> None:
        self.ticket = ticket
        self.raises = raises
        self.calls: list[dict[str, Any]] = []

    def execute(self, **kwargs: Any) -> ParkingTicket:
        self.calls.append(kwargs)
        if self.raises is not None:
            raise self.raises
        assert self.ticket is not None
        return self.ticket


class FakeEventPublisher:
    def __init__(self) -> None:
        self.published: list[object] = []

    def publish(self, event: object) -> None:
        self.published.append(event)


def _make_vehicle(vehicle_id: UUID, user_id: UUID) -> Vehicle:
    return Vehicle(
        id=vehicle_id,
        brand=Brand.GENERIC,
        display_name="Test Vehicle",
        vin=None,
        license_plate="1234ABC",
        created_at=datetime.now(UTC),
        user_id=user_id,
    )


def _make_ser_zone(zone_number: str = "163") -> SerZone:
    return SerZone(
        city_code="madrid",
        zone_number=zone_number,
        zone_type="Azul",
        district="CENTRO",
        spot_count=15,
        geometry=_SQUARE,
    )


def _make_ticket(vehicle_id: UUID, user_id: UUID) -> ParkingTicket:
    return ParkingTicket(
        id=uuid4(),
        vehicle_id=vehicle_id,
        user_id=user_id,
        provider="elparking",
        duration_minutes=60,
        provider_reference="ref-123",
        cost=1.5,
        end_date=datetime(2026, 7, 26, 12, 0, tzinfo=UTC),
        created_at=datetime(2026, 7, 26, 10, 0, tzinfo=UTC),
        city_code="madrid",
        zone_number="163",
        # Distinct from created_at — proves SerTicketCreated uses the real
        # start_date, not the moment our own record was written.
        start_date=datetime(2026, 7, 26, 9, 0, tzinfo=UTC),
    )


def _make_event(vehicle_id: UUID, lat: float, lng: float, now: datetime) -> VehicleLocationUpdated:
    return VehicleLocationUpdated(
        vehicle_id=vehicle_id,
        latitude=lat,
        longitude=lng,
        recorded_at=now,
        received_at=now,
        source="push",
    )


class _Fixture:
    def __init__(self) -> None:
        self.vehicle_repo = FakeVehicleRepo()
        self.preferences_repo = FakeUserPreferencesRepo()
        self.provider_config_repo = FakeUserSerProviderConfigRepo()
        self.determine_requirement = FakeDetermineSerTicketRequirement(required=True)
        self.ser_zone_recheck_gate = FakeSerZoneRecheckGate()
        self.create_ser_ticket = FakeCreateSerTicket()
        self.event_publisher = FakeEventPublisher()

    def build(self) -> SerTicketCreationTriggerHandler:
        return SerTicketCreationTriggerHandler(
            vehicle_repo=self.vehicle_repo,  # type: ignore[arg-type]
            user_preferences_repo=self.preferences_repo,  # type: ignore[arg-type]
            user_ser_provider_config_repo=self.provider_config_repo,  # type: ignore[arg-type]
            determine_ser_ticket_requirement=self.determine_requirement,  # type: ignore[arg-type]
            ser_zone_recheck_gate=self.ser_zone_recheck_gate,  # type: ignore[arg-type]
            create_ser_ticket=self.create_ser_ticket,  # type: ignore[arg-type]
            event_publisher=self.event_publisher,  # type: ignore[arg-type]
        )


def test_ticket_created_when_gate_signals_check_and_requirement_is_true() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.preferences_repo.set(user_id, auto_create_ticket=True, default_ticket_duration_minutes=90)
    fx.provider_config_repo.set_connected(user_id, ["elparking"])
    fx.ser_zone_recheck_gate.decision = SerZoneRecheckDecision(
        should_check=True, zone=_make_ser_zone(zone_number="163")
    )
    fx.create_ser_ticket.ticket = _make_ticket(vehicle_id, user_id)
    handler = fx.build()

    handler.handle(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert len(fx.create_ser_ticket.calls) == 1
    call = fx.create_ser_ticket.calls[0]
    assert call["provider"] == "elparking"
    assert call["duration_minutes"] == 90
    assert call["location"] == GeoLocation(lat=_MOVED_LAT, lng=_MOVED_LNG)
    assert call["auto_created"] is True
    assert len(fx.event_publisher.published) == 1
    published = fx.event_publisher.published[0]
    assert isinstance(published, SerTicketCreated)
    assert published.zone_number == "163"
    assert published.start_date == fx.create_ser_ticket.ticket.start_date
    assert published.end_date == fx.create_ser_ticket.ticket.end_date
    assert fx.determine_requirement.calls == [(fx.ser_zone_recheck_gate.decision.zone, vehicle_id)]


def test_gate_called_with_creation_zone_change_floor(monkeypatch) -> None:
    monkeypatch.setenv("SER_TICKET_CREATION_ZONE_CHANGE_FLOOR_METERS", "17")
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.preferences_repo.set(user_id, auto_create_ticket=True)
    fx.ser_zone_recheck_gate.decision = SerZoneRecheckDecision(should_check=False, zone=None)
    handler = fx.build()

    handler.handle(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert len(fx.ser_zone_recheck_gate.calls) == 1
    _event, floor = fx.ser_zone_recheck_gate.calls[0]
    assert floor == 17


def test_no_creation_when_auto_create_ticket_disabled() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.preferences_repo.set(user_id, auto_create_ticket=False)
    handler = fx.build()

    handler.handle(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert fx.ser_zone_recheck_gate.calls == []
    assert fx.create_ser_ticket.calls == []
    assert fx.event_publisher.published == []


def test_ser_zone_recheck_gate_signals_no_check_needed() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.preferences_repo.set(user_id, auto_create_ticket=True)
    fx.ser_zone_recheck_gate.decision = SerZoneRecheckDecision(should_check=False, zone=None)
    handler = fx.build()

    handler.handle(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert fx.determine_requirement.calls == []
    assert fx.create_ser_ticket.calls == []
    assert fx.event_publisher.published == []


def test_stationary_vehicle_with_no_active_ticket_still_gets_rechecked() -> None:
    """
    SerZoneRecheckGate always signals should_check=True for a vehicle with no
    active ParkingTicket, even for unchanged coordinates (see
    ser-zone-recheck-gate spec.md) — from the handler's perspective, this
    means DetermineSerTicketRequirement is still called for the resolved zone.
    """
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.preferences_repo.set(user_id, auto_create_ticket=True)
    zone = _make_ser_zone(zone_number="163")
    fx.ser_zone_recheck_gate.decision = SerZoneRecheckDecision(should_check=True, zone=zone)
    fx.determine_requirement.required = False
    handler = fx.build()

    handler.handle(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert fx.determine_requirement.calls == [(zone, vehicle_id)]
    assert fx.create_ser_ticket.calls == []


def test_no_ticket_required_outside_all_zones() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.preferences_repo.set(user_id, auto_create_ticket=True)
    fx.ser_zone_recheck_gate.decision = SerZoneRecheckDecision(should_check=True, zone=None)
    fx.determine_requirement.required = False
    handler = fx.build()

    handler.handle(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert fx.create_ser_ticket.calls == []
    assert fx.event_publisher.published == []


def test_matching_exemption_suppresses_ticket_creation() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.preferences_repo.set(user_id, auto_create_ticket=True)
    fx.ser_zone_recheck_gate.decision = SerZoneRecheckDecision(should_check=True, zone=_make_ser_zone())
    fx.determine_requirement.required = False  # matching exemption
    handler = fx.build()

    handler.handle(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert fx.create_ser_ticket.calls == []


def test_no_creation_when_ticket_required_but_zone_is_none() -> None:
    """
    Defensive branch: if DetermineSerTicketRequirement ever returned True for
    a None zone, the handler must not proceed to build a ticket that needs
    zone.zone_number (would raise AttributeError) — it returns instead.
    """
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.preferences_repo.set(user_id, auto_create_ticket=True)
    fx.ser_zone_recheck_gate.decision = SerZoneRecheckDecision(should_check=True, zone=None)
    fx.determine_requirement.required = True
    handler = fx.build()

    handler.handle(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert fx.create_ser_ticket.calls == []
    assert fx.event_publisher.published == []


def test_missing_vehicle_skipped_without_error() -> None:
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()  # no vehicle registered
    handler = fx.build()

    result = handler.handle(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert result is None
    assert fx.ser_zone_recheck_gate.calls == []
    assert fx.create_ser_ticket.calls == []
    assert fx.event_publisher.published == []


def test_ticket_created_records_created_outcome_metric(monkeypatch) -> None:
    recorded: list[str] = []
    monkeypatch.setattr(
        "mobility_manager.application.event_handlers.ser_ticket_creation_trigger_handler.record_ser_ticket_auto_creation",
        lambda outcome: recorded.append(outcome),
    )
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.preferences_repo.set(user_id, auto_create_ticket=True)
    fx.provider_config_repo.set_connected(user_id, ["elparking"])
    fx.ser_zone_recheck_gate.decision = SerZoneRecheckDecision(
        should_check=True, zone=_make_ser_zone(zone_number="163")
    )
    fx.create_ser_ticket.ticket = _make_ticket(vehicle_id, user_id)
    handler = fx.build()

    handler.handle(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert recorded == ["created"]


def test_ticket_creation_failure_records_failed_outcome_metric(monkeypatch) -> None:
    recorded: list[str] = []
    monkeypatch.setattr(
        "mobility_manager.application.event_handlers.ser_ticket_creation_trigger_handler.record_ser_ticket_auto_creation",
        lambda outcome: recorded.append(outcome),
    )
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.preferences_repo.set(user_id, auto_create_ticket=True)
    fx.provider_config_repo.set_connected(user_id, ["elparking"])
    fx.ser_zone_recheck_gate.decision = SerZoneRecheckDecision(
        should_check=True, zone=_make_ser_zone(zone_number="163")
    )
    fx.create_ser_ticket.raises = SerProviderApiError("boom")
    handler = fx.build()

    handler.handle(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert recorded == ["failed"]


def test_no_connected_provider_publishes_creation_failed_without_calling_create_ser_ticket() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.preferences_repo.set(user_id, auto_create_ticket=True)
    fx.ser_zone_recheck_gate.decision = SerZoneRecheckDecision(
        should_check=True, zone=_make_ser_zone(zone_number="163")
    )
    # no provider connected
    handler = fx.build()

    handler.handle(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert fx.create_ser_ticket.calls == []
    assert len(fx.event_publisher.published) == 1
    published = fx.event_publisher.published[0]
    assert isinstance(published, SerTicketCreationFailed)
    assert published.reason == "no_provider_connected"
    assert published.zone_number == "163"


class TestFailureReasonMapping:
    def _run(self, exc: Exception) -> SerTicketCreationFailed:
        vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
        fx = _Fixture()
        fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
        fx.preferences_repo.set(user_id, auto_create_ticket=True)
        fx.provider_config_repo.set_connected(user_id, ["elparking"])
        fx.ser_zone_recheck_gate.decision = SerZoneRecheckDecision(
            should_check=True, zone=_make_ser_zone(zone_number="163")
        )
        fx.create_ser_ticket.raises = exc
        handler = fx.build()

        handler.handle(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

        assert len(fx.event_publisher.published) == 1
        published = fx.event_publisher.published[0]
        assert isinstance(published, SerTicketCreationFailed)
        return published

    def test_session_not_found_maps_to_no_provider_session(self) -> None:
        published = self._run(SerProviderSessionNotFoundError("no session"))
        assert published.reason == "no_provider_session"
        assert "no session" not in (published.reason or "")

    def test_zone_not_found_maps_to_zone_not_found(self) -> None:
        published = self._run(SerZoneNotFoundError("boom"))
        assert published.reason == "zone_not_found"

    def test_vehicle_not_found_maps_to_vehicle_not_matched(self) -> None:
        published = self._run(SerProviderVehicleNotFoundError("boom"))
        assert published.reason == "vehicle_not_matched"

    def test_provider_api_error_maps_to_provider_error(self) -> None:
        published = self._run(SerProviderApiError("boom"))
        assert published.reason == "provider_error"

    def test_unexpected_exception_maps_to_provider_error(self) -> None:
        published = self._run(RuntimeError("some secret detail"))
        assert published.reason == "provider_error"
        assert "some secret detail" not in published.reason

    def test_persistence_error_maps_to_ticket_created_but_not_recorded(self) -> None:
        published = self._run(SerTicketPersistenceError("charged but not saved"))
        assert published.reason == "ticket_created_but_not_recorded"
        assert "charged but not saved" not in published.reason
