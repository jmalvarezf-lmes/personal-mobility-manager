"""
Unit tests for SerTicketCreationTriggerHandler.

Covers every scenario in the ser-ticket-auto-creation spec: ticket created
when required and the movement threshold is met, no-op when
auto_create_ticket is disabled, movement-threshold skip, no-zone/exemption
skip, missing-vehicle skip, and each mapped failure reason (mocked ports,
no real DB).
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from shapely.geometry import Polygon

from mobility_manager.application.event_handlers.ser_ticket_creation_trigger_handler import (
    SerTicketCreationTriggerHandler,
)
from mobility_manager.domain.entities.parking_ticket import ParkingTicket
from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.entities.user_notification_preference import (
    UserNotificationPreference,
)
from mobility_manager.domain.entities.user_preferences import UserPreferences
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.entities.vehicle_location import VehicleLocation
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

_FAR_LAT, _FAR_LNG = 40.4168, -3.7038
_MOVED_LAT, _MOVED_LNG = 40.4258, -3.7038  # ~1km north of _FAR_*
_NEAR_LAT, _NEAR_LNG = 40.4169, -3.7037  # ~15m from _FAR_*, well under 50m

_SQUARE = Polygon([(440584, 4474459), (440604, 4474459), (440604, 4474479), (440584, 4474479)])

_TYPE_KEY = "ser_zone_ticket_required"


class FakeVehicleRepo:
    def __init__(self) -> None:
        self.vehicles: dict[UUID, Vehicle] = {}

    def add(self, vehicle: Vehicle) -> None:
        self.vehicles[vehicle.id] = vehicle

    def get_by_id(self, vehicle_id: UUID) -> Vehicle | None:
        return self.vehicles.get(vehicle_id)


class FakeVehicleLocationRepo:
    def __init__(self) -> None:
        self.previous: VehicleLocation | None = None

    def get_previous(self, vehicle_id: UUID, before: datetime) -> VehicleLocation | None:
        return self.previous


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


class FakeNotificationPreferencesRepo:
    def __init__(self) -> None:
        self._rows: dict[tuple[UUID, str], UserNotificationPreference] = {}

    def set(self, user_id: UUID, type_key: str, enabled: bool, config: dict[str, Any] | None = None) -> None:
        self._rows[(user_id, type_key)] = UserNotificationPreference(
            user_id=user_id,
            type_key=type_key,
            enabled=enabled,
            config=config or {},
            updated_at=datetime.now(UTC),
        )

    def find_by_user_id_and_type(self, user_id: UUID, type_key: str) -> UserNotificationPreference | None:
        return self._rows.get((user_id, type_key))


class FakeUserSerProviderConfigRepo:
    def __init__(self) -> None:
        self.connected: dict[UUID, list[str]] = {}

    def set_connected(self, user_id: UUID, providers: list[str]) -> None:
        self.connected[user_id] = providers

    def list_connected_providers(self, user_id: UUID) -> list[str]:
        return self.connected.get(user_id, [])


class FakeFindContainingSerZone:
    def __init__(self) -> None:
        self.zone: SerZone | None = None
        self.calls: list[GeoLocation] = []

    def execute(self, location: GeoLocation) -> SerZone | None:
        self.calls.append(location)
        return self.zone


class FakeDetermineSerTicketRequirement:
    def __init__(self, required: bool = True) -> None:
        self.required = required
        self.calls: list[tuple[SerZone | None, UUID]] = []

    def execute(self, zone: SerZone | None, vehicle_id: UUID, at=None) -> bool:
        self.calls.append((zone, vehicle_id))
        return self.required


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
        self.location_repo = FakeVehicleLocationRepo()
        self.preferences_repo = FakeUserPreferencesRepo()
        self.notification_preferences_repo = FakeNotificationPreferencesRepo()
        self.provider_config_repo = FakeUserSerProviderConfigRepo()
        self.find_containing = FakeFindContainingSerZone()
        self.determine_requirement = FakeDetermineSerTicketRequirement(required=True)
        self.create_ser_ticket = FakeCreateSerTicket()
        self.event_publisher = FakeEventPublisher()

    def build(self) -> SerTicketCreationTriggerHandler:
        return SerTicketCreationTriggerHandler(
            vehicle_repo=self.vehicle_repo,  # type: ignore[arg-type]
            vehicle_location_repo=self.location_repo,  # type: ignore[arg-type]
            user_preferences_repo=self.preferences_repo,  # type: ignore[arg-type]
            notification_preferences_repo=self.notification_preferences_repo,  # type: ignore[arg-type]
            user_ser_provider_config_repo=self.provider_config_repo,  # type: ignore[arg-type]
            find_containing_ser_zone=self.find_containing,  # type: ignore[arg-type]
            determine_ser_ticket_requirement=self.determine_requirement,  # type: ignore[arg-type]
            create_ser_ticket=self.create_ser_ticket,  # type: ignore[arg-type]
            event_publisher=self.event_publisher,  # type: ignore[arg-type]
        )


def test_ticket_created_when_required_and_threshold_met(monkeypatch) -> None:
    monkeypatch.setenv("DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS", "50")
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.preferences_repo.set(user_id, auto_create_ticket=True, default_ticket_duration_minutes=90)
    fx.provider_config_repo.set_connected(user_id, ["elparking"])
    fx.find_containing.zone = _make_ser_zone(zone_number="163")
    fx.create_ser_ticket.ticket = _make_ticket(vehicle_id, user_id)
    handler = fx.build()

    handler.handle(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert len(fx.create_ser_ticket.calls) == 1
    call = fx.create_ser_ticket.calls[0]
    assert call["provider"] == "elparking"
    assert call["duration_minutes"] == 90
    assert call["location"] == GeoLocation(lat=_MOVED_LAT, lng=_MOVED_LNG)
    assert len(fx.event_publisher.published) == 1
    published = fx.event_publisher.published[0]
    assert isinstance(published, SerTicketCreated)
    assert published.zone_number == "163"
    assert published.start_date == fx.create_ser_ticket.ticket.created_at
    assert published.end_date == fx.create_ser_ticket.ticket.end_date


def test_no_creation_when_auto_create_ticket_disabled() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.preferences_repo.set(user_id, auto_create_ticket=False)
    fx.find_containing.zone = _make_ser_zone()
    handler = fx.build()

    handler.handle(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert fx.create_ser_ticket.calls == []
    assert fx.event_publisher.published == []


def test_movement_below_threshold_skips_zone_check(monkeypatch) -> None:
    monkeypatch.setenv("DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS", "50")
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.preferences_repo.set(user_id, auto_create_ticket=True)
    fx.location_repo.previous = VehicleLocation(
        id=uuid4(),
        vehicle_id=vehicle_id,
        latitude=_FAR_LAT,
        longitude=_FAR_LNG,
        recorded_at=now,
        received_at=now,
        source="push",
    )
    handler = fx.build()

    handler.handle(_make_event(vehicle_id, _NEAR_LAT, _NEAR_LNG, now))

    assert fx.find_containing.calls == []
    assert fx.create_ser_ticket.calls == []
    assert fx.event_publisher.published == []


def test_no_ticket_required_outside_all_zones() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.preferences_repo.set(user_id, auto_create_ticket=True)
    fx.find_containing.zone = None
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
    fx.find_containing.zone = _make_ser_zone()
    fx.determine_requirement.required = False  # matching exemption
    handler = fx.build()

    handler.handle(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert fx.create_ser_ticket.calls == []


def test_no_creation_when_ticket_required_but_zone_is_none() -> None:
    """
    Defensive branch mirroring SerTicketNotificationTriggerHandler's
    identical guard: if DetermineSerTicketRequirement ever returned True for
    a None zone, the handler must not proceed to build a ticket that needs
    zone.zone_number (would raise AttributeError) — it returns instead.
    """
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.preferences_repo.set(user_id, auto_create_ticket=True)
    fx.find_containing.zone = None
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
    assert fx.find_containing.calls == []
    assert fx.create_ser_ticket.calls == []
    assert fx.event_publisher.published == []


def test_ticket_created_records_created_outcome_metric(monkeypatch) -> None:
    monkeypatch.setenv("DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS", "50")
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
    fx.find_containing.zone = _make_ser_zone(zone_number="163")
    fx.create_ser_ticket.ticket = _make_ticket(vehicle_id, user_id)
    handler = fx.build()

    handler.handle(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert recorded == ["created"]


def test_ticket_creation_failure_records_failed_outcome_metric(monkeypatch) -> None:
    monkeypatch.setenv("DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS", "50")
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
    fx.find_containing.zone = _make_ser_zone(zone_number="163")
    fx.create_ser_ticket.raises = SerProviderApiError("boom")
    handler = fx.build()

    handler.handle(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert recorded == ["failed"]


def test_no_connected_provider_publishes_creation_failed_without_calling_create_ser_ticket() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.preferences_repo.set(user_id, auto_create_ticket=True)
    fx.find_containing.zone = _make_ser_zone(zone_number="163")
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
        fx.find_containing.zone = _make_ser_zone(zone_number="163")
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
