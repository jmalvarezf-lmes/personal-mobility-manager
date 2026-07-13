"""
Unit tests for SerTicketTriggerHandler.

Covers every scenario in the ser-zone-ticket-notification and
vehicle-location-events specs: movement below threshold skips the zone
lookup entirely, a vehicle's first-ever recorded location still triggers a
zone check, genuine movement triggers a zone check, no notification when
DetermineSerTicketRequirement returns False, a notification with the
correct plate/zone_number when it returns True, a missing vehicle is
skipped without error, and the message is localized to the owner's
notification_language (or falls back to the default when unset). Also
confirms no ticket-provider or ticket-creation code path is ever exercised.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from shapely.geometry import Polygon

from mobility_manager.application.event_handlers.ser_ticket_trigger_handler import (
    SerTicketTriggerHandler,
)
from mobility_manager.config import get_notification_movement_threshold_meters
from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.entities.user_preferences import UserPreferences
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.entities.vehicle_location import VehicleLocation
from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.domain.value_objects.location import GeoLocation, distance_m
from mobility_manager.domain.value_objects.notification_message import (
    NotificationMessage,
)

# Madrid city-centre coordinates, ~1km apart — comfortably past the default
# 50m threshold. The "close" pair is a few metres apart — comfortably under it.
_FAR_LAT, _FAR_LNG = 40.4168, -3.7038
_NEAR_LAT, _NEAR_LNG = 40.4169, -3.7037  # ~15m away from _FAR_*, well under 50m
_MOVED_LAT, _MOVED_LNG = 40.4258, -3.7038  # ~1km north of _FAR_*

_SQUARE = Polygon([(440584, 4474459), (440604, 4474459), (440604, 4474479), (440584, 4474479)])


@pytest.fixture(autouse=True)
def _threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTIFICATION_MOVEMENT_THRESHOLD_METERS", "50")


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

    def set(self, user_id: UUID, notification_language: str | None) -> None:
        self.preferences[user_id] = UserPreferences(
            user_id=user_id,
            default_ticket_duration_minutes=60,
            auto_create_ticket=False,
            preferred_notification_channel="telegram",
            notification_language=notification_language,
            updated_at=datetime.now(UTC),
        )

    def find_by_user_id(self, user_id: UUID) -> UserPreferences | None:
        return self.preferences.get(user_id)


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
        self.calls: list[SerZone | None] = []

    def execute(self, zone: SerZone | None) -> bool:
        self.calls.append(zone)
        return self.required


class FakeSendNotification:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, NotificationMessage]] = []

    def execute(self, user_id: UUID, message: NotificationMessage) -> bool:
        self.calls.append((user_id, message))
        return True


def _make_vehicle(vehicle_id: UUID, user_id: UUID, license_plate: str | None = "1234ABC") -> Vehicle:
    return Vehicle(
        id=vehicle_id,
        brand=Brand.GENERIC,
        display_name="Test Vehicle",
        vin=None,
        license_plate=license_plate,
        created_at=datetime.now(UTC),
        user_id=user_id,
    )


def _make_previous_location(vehicle_id: UUID, lat: float, lng: float, recorded_at: datetime) -> VehicleLocation:
    return VehicleLocation(
        id=uuid4(),
        vehicle_id=vehicle_id,
        latitude=lat,
        longitude=lng,
        recorded_at=recorded_at,
        received_at=recorded_at,
        source="push",
    )


def _make_ser_zone(zone_number: str = "163") -> SerZone:
    return SerZone(
        zone_number=zone_number,
        zone_type="Azul",
        district="CENTRO",
        spot_count=15,
        geometry=_SQUARE,
    )


def _make_handler(
    vehicle_repo: FakeVehicleRepo,
    location_repo: FakeVehicleLocationRepo,
    preferences_repo: FakeUserPreferencesRepo,
    find_containing_ser_zone: FakeFindContainingSerZone,
    determine_ser_ticket_requirement: FakeDetermineSerTicketRequirement,
    send_notification: FakeSendNotification,
) -> SerTicketTriggerHandler:
    return SerTicketTriggerHandler(
        vehicle_repo=vehicle_repo,  # type: ignore[arg-type]
        vehicle_location_repo=location_repo,  # type: ignore[arg-type]
        user_preferences_repo=preferences_repo,  # type: ignore[arg-type]
        find_containing_ser_zone=find_containing_ser_zone,  # type: ignore[arg-type]
        determine_ser_ticket_requirement=determine_ser_ticket_requirement,  # type: ignore[arg-type]
        send_notification=send_notification,  # type: ignore[arg-type]
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


def test_skips_when_movement_below_threshold() -> None:
    vehicle_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)

    vehicle_repo = FakeVehicleRepo()
    vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    location_repo = FakeVehicleLocationRepo()
    location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    preferences_repo = FakeUserPreferencesRepo()
    find_containing = FakeFindContainingSerZone()
    find_containing.zone = _make_ser_zone()
    determine_requirement = FakeDetermineSerTicketRequirement(required=True)
    send_notification = FakeSendNotification()
    handler = _make_handler(
        vehicle_repo, location_repo, preferences_repo, find_containing, determine_requirement, send_notification
    )

    event = _make_event(vehicle_id, _NEAR_LAT, _NEAR_LNG, now)

    handler.handle(event)

    assert find_containing.calls == []
    assert determine_requirement.calls == []
    assert send_notification.calls == []


def test_checks_zone_when_movement_exactly_equals_threshold() -> None:
    """
    The comparison in the handler is strict `distance < threshold`, so a
    distance exactly equal to the configured threshold must be treated as
    "moved enough" (proceeds to the zone check), not as unchanged.
    """
    vehicle_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)

    threshold_meters = get_notification_movement_threshold_meters()
    # Binary-search a latitude offset so the *measured* distance (via the
    # same UTM projection distance_m uses) lands as close to
    # threshold_meters as floating point allows, rather than assuming a
    # fixed degrees-per-metre approximation holds exactly.
    low, high = 0.0, 0.01
    for _ in range(60):
        mid = (low + high) / 2
        measured = distance_m(_FAR_LAT, _FAR_LNG, _FAR_LAT + mid, _FAR_LNG)
        if measured < threshold_meters:
            low = mid
        else:
            high = mid
    # `high` is the smallest offset found where measured distance is not
    # below the threshold (i.e. >= threshold) — use it so the resulting
    # point is guaranteed to trigger the ">= threshold" branch.
    exact_lat, exact_lng = _FAR_LAT + high, _FAR_LNG
    measured_distance = distance_m(_FAR_LAT, _FAR_LNG, exact_lat, exact_lng)
    assert measured_distance == pytest.approx(threshold_meters, abs=1e-6)
    assert not (measured_distance < threshold_meters)  # exactly at threshold, not below it

    vehicle_repo = FakeVehicleRepo()
    vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    location_repo = FakeVehicleLocationRepo()
    location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    preferences_repo = FakeUserPreferencesRepo()
    find_containing = FakeFindContainingSerZone()
    find_containing.zone = None
    determine_requirement = FakeDetermineSerTicketRequirement(required=False)
    send_notification = FakeSendNotification()
    handler = _make_handler(
        vehicle_repo, location_repo, preferences_repo, find_containing, determine_requirement, send_notification
    )

    event = _make_event(vehicle_id, exact_lat, exact_lng, now)

    handler.handle(event)

    assert len(find_containing.calls) == 1


def test_checks_zone_on_first_ever_location() -> None:
    vehicle_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)

    vehicle_repo = FakeVehicleRepo()
    vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    location_repo = FakeVehicleLocationRepo()
    location_repo.previous = None  # first-ever location
    preferences_repo = FakeUserPreferencesRepo()
    find_containing = FakeFindContainingSerZone()
    find_containing.zone = None
    determine_requirement = FakeDetermineSerTicketRequirement(required=False)
    send_notification = FakeSendNotification()
    handler = _make_handler(
        vehicle_repo, location_repo, preferences_repo, find_containing, determine_requirement, send_notification
    )

    event = _make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now)

    handler.handle(event)

    assert len(find_containing.calls) == 1
    assert find_containing.calls[0].lat == _MOVED_LAT
    assert find_containing.calls[0].lng == _MOVED_LNG


def test_checks_zone_on_genuine_movement() -> None:
    vehicle_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)

    vehicle_repo = FakeVehicleRepo()
    vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    location_repo = FakeVehicleLocationRepo()
    location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    preferences_repo = FakeUserPreferencesRepo()
    find_containing = FakeFindContainingSerZone()
    find_containing.zone = None
    determine_requirement = FakeDetermineSerTicketRequirement(required=False)
    send_notification = FakeSendNotification()
    handler = _make_handler(
        vehicle_repo, location_repo, preferences_repo, find_containing, determine_requirement, send_notification
    )

    event = _make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now)

    handler.handle(event)

    assert len(find_containing.calls) == 1


def test_skips_notification_when_ticket_not_required() -> None:
    vehicle_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)

    vehicle_repo = FakeVehicleRepo()
    vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    location_repo = FakeVehicleLocationRepo()
    location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    preferences_repo = FakeUserPreferencesRepo()
    find_containing = FakeFindContainingSerZone()
    find_containing.zone = None
    determine_requirement = FakeDetermineSerTicketRequirement(required=False)
    send_notification = FakeSendNotification()
    handler = _make_handler(
        vehicle_repo, location_repo, preferences_repo, find_containing, determine_requirement, send_notification
    )

    event = _make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now)

    handler.handle(event)

    assert send_notification.calls == []


def test_sends_notification_with_correct_plate_and_zone_number() -> None:
    vehicle_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)

    vehicle_repo = FakeVehicleRepo()
    vehicle_repo.add(_make_vehicle(vehicle_id, user_id, license_plate="1234ABC"))
    location_repo = FakeVehicleLocationRepo()
    location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    preferences_repo = FakeUserPreferencesRepo()
    preferences_repo.set(user_id, None)
    find_containing = FakeFindContainingSerZone()
    find_containing.zone = _make_ser_zone(zone_number="163")
    determine_requirement = FakeDetermineSerTicketRequirement(required=True)
    send_notification = FakeSendNotification()
    handler = _make_handler(
        vehicle_repo, location_repo, preferences_repo, find_containing, determine_requirement, send_notification
    )

    event = _make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now)

    handler.handle(event)

    assert len(send_notification.calls) == 1
    called_user_id, message = send_notification.calls[0]
    assert called_user_id == user_id
    assert "1234ABC" in message.text
    assert "163" in message.text
    assert message.location is not None
    assert message.location.lat == _MOVED_LAT
    assert message.location.lng == _MOVED_LNG


def test_missing_vehicle_is_skipped_without_error() -> None:
    vehicle_id = uuid4()
    now = datetime.now(UTC)

    vehicle_repo = FakeVehicleRepo()  # no vehicle registered
    location_repo = FakeVehicleLocationRepo()
    location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    preferences_repo = FakeUserPreferencesRepo()
    find_containing = FakeFindContainingSerZone()
    find_containing.zone = _make_ser_zone()
    determine_requirement = FakeDetermineSerTicketRequirement(required=True)
    send_notification = FakeSendNotification()
    handler = _make_handler(
        vehicle_repo, location_repo, preferences_repo, find_containing, determine_requirement, send_notification
    )

    event = _make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now)

    result = handler.handle(event)

    assert result is None
    assert find_containing.calls == []
    assert determine_requirement.calls == []
    assert send_notification.calls == []


def test_message_localized_to_owner_notification_language() -> None:
    vehicle_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)

    vehicle_repo = FakeVehicleRepo()
    vehicle_repo.add(_make_vehicle(vehicle_id, user_id, license_plate="9999ZZZ"))
    location_repo = FakeVehicleLocationRepo()
    location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    preferences_repo = FakeUserPreferencesRepo()
    preferences_repo.set(user_id, "es")
    find_containing = FakeFindContainingSerZone()
    find_containing.zone = _make_ser_zone(zone_number="163")
    determine_requirement = FakeDetermineSerTicketRequirement(required=True)
    send_notification = FakeSendNotification()
    handler = _make_handler(
        vehicle_repo, location_repo, preferences_repo, find_containing, determine_requirement, send_notification
    )

    event = _make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now)

    handler.handle(event)

    assert len(send_notification.calls) == 1
    _, message = send_notification.calls[0]
    assert message.text == (
        "Tu coche con matrícula 9999ZZZ está en la zona SER 163 — necesitas crear un tique de estacionamiento."
    )


def test_message_falls_back_to_default_language_when_unset() -> None:
    vehicle_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)

    vehicle_repo = FakeVehicleRepo()
    vehicle_repo.add(_make_vehicle(vehicle_id, user_id, license_plate="9999ZZZ"))
    location_repo = FakeVehicleLocationRepo()
    location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    preferences_repo = FakeUserPreferencesRepo()  # no preferences row at all
    find_containing = FakeFindContainingSerZone()
    find_containing.zone = _make_ser_zone(zone_number="163")
    determine_requirement = FakeDetermineSerTicketRequirement(required=True)
    send_notification = FakeSendNotification()
    handler = _make_handler(
        vehicle_repo, location_repo, preferences_repo, find_containing, determine_requirement, send_notification
    )

    event = _make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now)

    handler.handle(event)

    assert len(send_notification.calls) == 1
    _, message = send_notification.calls[0]
    assert message.text == "Your car with plate 9999ZZZ is in SER zone 163 — you need to create a parking ticket."


def test_no_ticket_provider_or_ticket_creation_code_path_is_exercised() -> None:
    """
    Guards the non-goal explicitly: this handler must never touch a
    SerTicketProvider or any ticket-creation use case, regardless of
    outcome. There is no such dependency injected into the handler at all,
    so this test asserts the constructor's dependency set stays exactly as
    scoped (no provider/create-ticket collaborator sneaks in).
    """
    import inspect

    params = inspect.signature(SerTicketTriggerHandler.__init__).parameters
    assert "ser_ticket_provider" not in params
    assert "create_ser_ticket" not in params
