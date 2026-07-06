"""
Unit tests for NotificationDispatchHandler.

Covers every scenario in the vehicle-location-notification spec: movement
past the threshold notifies, movement below the threshold doesn't, a
vehicle's first-ever recorded location doesn't, a deleted/missing vehicle is
skipped without error, and the message is localized to the owner's
notification_language (or falls back to the default when unset).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from mobility_manager.application.event_handlers.notification_dispatch_handler import (
    NotificationDispatchHandler,
)
from mobility_manager.domain.entities.user_preferences import UserPreferences
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.entities.vehicle_location import VehicleLocation
from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.domain.value_objects.notification_message import (
    NotificationMessage,
)

# Madrid city-centre coordinates, ~1km apart — comfortably past the default
# 50m threshold. The "close" pair is a few metres apart — comfortably under it.
_FAR_LAT, _FAR_LNG = 40.4168, -3.7038
_NEAR_LAT, _NEAR_LNG = 40.4169, -3.7037  # ~15m away from _FAR_*, well under 50m
_MOVED_LAT, _MOVED_LNG = 40.4258, -3.7038  # ~1km north of _FAR_*


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


def _make_handler(
    vehicle_repo: FakeVehicleRepo,
    location_repo: FakeVehicleLocationRepo,
    preferences_repo: FakeUserPreferencesRepo,
    send_notification: FakeSendNotification,
) -> NotificationDispatchHandler:
    return NotificationDispatchHandler(
        vehicle_repo=vehicle_repo,  # type: ignore[arg-type]
        vehicle_location_repo=location_repo,  # type: ignore[arg-type]
        user_preferences_repo=preferences_repo,  # type: ignore[arg-type]
        send_notification=send_notification,  # type: ignore[arg-type]
    )


def test_movement_past_threshold_triggers_notification() -> None:
    vehicle_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)

    vehicle_repo = FakeVehicleRepo()
    vehicle_repo.add(_make_vehicle(vehicle_id, user_id, license_plate="1234ABC"))
    location_repo = FakeVehicleLocationRepo()
    location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    preferences_repo = FakeUserPreferencesRepo()
    preferences_repo.set(user_id, None)
    send_notification = FakeSendNotification()
    handler = _make_handler(vehicle_repo, location_repo, preferences_repo, send_notification)

    event = VehicleLocationUpdated(
        vehicle_id=vehicle_id,
        latitude=_MOVED_LAT,
        longitude=_MOVED_LNG,
        recorded_at=now,
        source="push",
    )

    handler.handle(event)

    assert len(send_notification.calls) == 1
    called_user_id, message = send_notification.calls[0]
    assert called_user_id == user_id
    assert "1234ABC" in message.text
    assert message.location is not None
    assert message.location.lat == _MOVED_LAT
    assert message.location.lng == _MOVED_LNG


def test_movement_below_threshold_does_not_trigger_notification() -> None:
    vehicle_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)

    vehicle_repo = FakeVehicleRepo()
    vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    location_repo = FakeVehicleLocationRepo()
    location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    preferences_repo = FakeUserPreferencesRepo()
    preferences_repo.set(user_id, None)
    send_notification = FakeSendNotification()
    handler = _make_handler(vehicle_repo, location_repo, preferences_repo, send_notification)

    event = VehicleLocationUpdated(
        vehicle_id=vehicle_id,
        latitude=_NEAR_LAT,
        longitude=_NEAR_LNG,
        recorded_at=now,
        source="push",
    )

    handler.handle(event)

    assert send_notification.calls == []


def test_first_ever_location_does_not_trigger_notification() -> None:
    vehicle_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)

    vehicle_repo = FakeVehicleRepo()
    vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    location_repo = FakeVehicleLocationRepo()
    location_repo.previous = None  # first-ever location
    preferences_repo = FakeUserPreferencesRepo()
    send_notification = FakeSendNotification()
    handler = _make_handler(vehicle_repo, location_repo, preferences_repo, send_notification)

    event = VehicleLocationUpdated(
        vehicle_id=vehicle_id,
        latitude=_MOVED_LAT,
        longitude=_MOVED_LNG,
        recorded_at=now,
        source="push",
    )

    handler.handle(event)

    assert send_notification.calls == []


def test_missing_vehicle_is_skipped_without_error() -> None:
    vehicle_id = uuid4()
    now = datetime.now(UTC)

    vehicle_repo = FakeVehicleRepo()  # no vehicle registered
    location_repo = FakeVehicleLocationRepo()
    preferences_repo = FakeUserPreferencesRepo()
    send_notification = FakeSendNotification()
    handler = _make_handler(vehicle_repo, location_repo, preferences_repo, send_notification)

    event = VehicleLocationUpdated(
        vehicle_id=vehicle_id,
        latitude=_MOVED_LAT,
        longitude=_MOVED_LNG,
        recorded_at=now,
        source="push",
    )

    result = handler.handle(event)

    assert result is None
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
    send_notification = FakeSendNotification()
    handler = _make_handler(vehicle_repo, location_repo, preferences_repo, send_notification)

    event = VehicleLocationUpdated(
        vehicle_id=vehicle_id,
        latitude=_MOVED_LAT,
        longitude=_MOVED_LNG,
        recorded_at=now,
        source="push",
    )

    handler.handle(event)

    assert len(send_notification.calls) == 1
    _, message = send_notification.calls[0]
    assert message.text == "Tu coche con matrícula 9999ZZZ está ahora aquí."


def test_message_falls_back_to_default_language_when_unset() -> None:
    vehicle_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)

    vehicle_repo = FakeVehicleRepo()
    vehicle_repo.add(_make_vehicle(vehicle_id, user_id, license_plate="9999ZZZ"))
    location_repo = FakeVehicleLocationRepo()
    location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    preferences_repo = FakeUserPreferencesRepo()  # no preferences row at all
    send_notification = FakeSendNotification()
    handler = _make_handler(vehicle_repo, location_repo, preferences_repo, send_notification)

    event = VehicleLocationUpdated(
        vehicle_id=vehicle_id,
        latitude=_MOVED_LAT,
        longitude=_MOVED_LNG,
        recorded_at=now,
        source="push",
    )

    handler.handle(event)

    assert len(send_notification.calls) == 1
    _, message = send_notification.calls[0]
    assert message.text == "Your car with plate 9999ZZZ is now located here."
