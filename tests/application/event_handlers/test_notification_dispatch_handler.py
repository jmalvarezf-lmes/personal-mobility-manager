"""
Unit tests for NotificationDispatchHandler.

Covers every scenario in the vehicle-location-notification spec: a disabled
(or missing) `location_moved` preference skips before any location lookup,
movement past the effective threshold notifies, movement below the
effective threshold doesn't, a vehicle's first-ever recorded location
doesn't, a deleted/missing vehicle is skipped without error, per-user
threshold overrides are honored, missing config falls back to the env-var
default, and the message is localized to the owner's notification_language
(or falls back to the default when unset).
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from mobility_manager.application.event_handlers.notification_dispatch_handler import (
    NotificationDispatchHandler,
)
from mobility_manager.domain.entities.user_notification_preference import (
    UserNotificationPreference,
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

_TYPE_KEY = "location_moved"


@pytest.fixture(autouse=True)
def _threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS", "50")


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
        self.get_previous_calls: list[UUID] = []

    def get_previous(self, vehicle_id: UUID, before: datetime) -> VehicleLocation | None:
        self.get_previous_calls.append(vehicle_id)
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

    def list_types(self):  # pragma: no cover - not exercised by this handler
        raise NotImplementedError

    def ensure_defaults(self, user_id: UUID) -> None:  # pragma: no cover - not exercised by this handler
        raise NotImplementedError

    def find_by_user_id(self, user_id: UUID) -> list[UserNotificationPreference]:
        return [row for (uid, _), row in self._rows.items() if uid == user_id]

    def find_by_user_id_and_type(self, user_id: UUID, type_key: str) -> UserNotificationPreference | None:
        return self._rows.get((user_id, type_key))

    def update(self, user_id, type_key, enabled, config):  # pragma: no cover - not exercised by this handler
        raise NotImplementedError


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
    notification_preferences_repo: FakeNotificationPreferencesRepo,
    send_notification: FakeSendNotification,
) -> NotificationDispatchHandler:
    return NotificationDispatchHandler(
        vehicle_repo=vehicle_repo,  # type: ignore[arg-type]
        vehicle_location_repo=location_repo,  # type: ignore[arg-type]
        user_preferences_repo=preferences_repo,  # type: ignore[arg-type]
        notification_preferences_repo=notification_preferences_repo,  # type: ignore[arg-type]
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
    notification_preferences_repo = FakeNotificationPreferencesRepo()
    notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True)
    send_notification = FakeSendNotification()
    handler = _make_handler(
        vehicle_repo, location_repo, preferences_repo, notification_preferences_repo, send_notification
    )

    event = VehicleLocationUpdated(
        vehicle_id=vehicle_id,
        latitude=_MOVED_LAT,
        longitude=_MOVED_LNG,
        recorded_at=now,
        received_at=now,
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
    notification_preferences_repo = FakeNotificationPreferencesRepo()
    notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True)
    send_notification = FakeSendNotification()
    handler = _make_handler(
        vehicle_repo, location_repo, preferences_repo, notification_preferences_repo, send_notification
    )

    event = VehicleLocationUpdated(
        vehicle_id=vehicle_id,
        latitude=_NEAR_LAT,
        longitude=_NEAR_LNG,
        recorded_at=now,
        received_at=now,
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
    notification_preferences_repo = FakeNotificationPreferencesRepo()
    notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True)
    send_notification = FakeSendNotification()
    handler = _make_handler(
        vehicle_repo, location_repo, preferences_repo, notification_preferences_repo, send_notification
    )

    event = VehicleLocationUpdated(
        vehicle_id=vehicle_id,
        latitude=_MOVED_LAT,
        longitude=_MOVED_LNG,
        recorded_at=now,
        received_at=now,
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
    notification_preferences_repo = FakeNotificationPreferencesRepo()
    send_notification = FakeSendNotification()
    handler = _make_handler(
        vehicle_repo, location_repo, preferences_repo, notification_preferences_repo, send_notification
    )

    event = VehicleLocationUpdated(
        vehicle_id=vehicle_id,
        latitude=_MOVED_LAT,
        longitude=_MOVED_LNG,
        recorded_at=now,
        received_at=now,
        source="push",
    )

    result = handler.handle(event)

    assert result is None
    assert send_notification.calls == []


def test_disabled_preference_skips_before_previous_location_lookup() -> None:
    """Disabled preference must skip before VehicleLocationRepository.get_previous is called at all."""
    vehicle_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)

    vehicle_repo = FakeVehicleRepo()
    vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    location_repo = FakeVehicleLocationRepo()
    location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    preferences_repo = FakeUserPreferencesRepo()
    notification_preferences_repo = FakeNotificationPreferencesRepo()
    notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=False)
    send_notification = FakeSendNotification()
    handler = _make_handler(
        vehicle_repo, location_repo, preferences_repo, notification_preferences_repo, send_notification
    )

    event = VehicleLocationUpdated(
        vehicle_id=vehicle_id,
        latitude=_MOVED_LAT,
        longitude=_MOVED_LNG,
        recorded_at=now,
        received_at=now,
        source="push",
    )

    handler.handle(event)

    assert send_notification.calls == []
    assert location_repo.get_previous_calls == []


def test_missing_preference_row_skips_before_previous_location_lookup() -> None:
    """A missing (never-provisioned) preference row is treated the same as disabled."""
    vehicle_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)

    vehicle_repo = FakeVehicleRepo()
    vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    location_repo = FakeVehicleLocationRepo()
    location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    preferences_repo = FakeUserPreferencesRepo()
    notification_preferences_repo = FakeNotificationPreferencesRepo()  # no row at all
    send_notification = FakeSendNotification()
    handler = _make_handler(
        vehicle_repo, location_repo, preferences_repo, notification_preferences_repo, send_notification
    )

    event = VehicleLocationUpdated(
        vehicle_id=vehicle_id,
        latitude=_MOVED_LAT,
        longitude=_MOVED_LNG,
        recorded_at=now,
        received_at=now,
        source="push",
    )

    handler.handle(event)

    assert send_notification.calls == []
    assert location_repo.get_previous_calls == []


def test_per_user_threshold_override_is_honored() -> None:
    """A user-configured threshold_m below the movement distance still triggers, even under the env-var default."""
    vehicle_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)

    vehicle_repo = FakeVehicleRepo()
    vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    location_repo = FakeVehicleLocationRepo()
    location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    preferences_repo = FakeUserPreferencesRepo()
    notification_preferences_repo = FakeNotificationPreferencesRepo()
    # _NEAR_* is ~15m from _FAR_* — under the 50m env default but over a 5m override.
    notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True, config={"threshold_m": 5})
    send_notification = FakeSendNotification()
    handler = _make_handler(
        vehicle_repo, location_repo, preferences_repo, notification_preferences_repo, send_notification
    )

    event = VehicleLocationUpdated(
        vehicle_id=vehicle_id,
        latitude=_NEAR_LAT,
        longitude=_NEAR_LNG,
        recorded_at=now,
        received_at=now,
        source="push",
    )

    handler.handle(event)

    assert len(send_notification.calls) == 1


def test_high_threshold_override_suppresses_notification() -> None:
    """A user-configured threshold_m above the movement distance suppresses a notification the env default would send."""
    vehicle_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)

    vehicle_repo = FakeVehicleRepo()
    vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    location_repo = FakeVehicleLocationRepo()
    location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    preferences_repo = FakeUserPreferencesRepo()
    notification_preferences_repo = FakeNotificationPreferencesRepo()
    # _MOVED_* is ~1km from _FAR_* — past the 50m default but under a 5000m override.
    notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True, config={"threshold_m": 5000})
    send_notification = FakeSendNotification()
    handler = _make_handler(
        vehicle_repo, location_repo, preferences_repo, notification_preferences_repo, send_notification
    )

    event = VehicleLocationUpdated(
        vehicle_id=vehicle_id,
        latitude=_MOVED_LAT,
        longitude=_MOVED_LNG,
        recorded_at=now,
        received_at=now,
        source="push",
    )

    handler.handle(event)

    assert send_notification.calls == []


def test_missing_config_falls_back_to_env_var_default() -> None:
    """An enabled preference with config={} resolves the threshold via the env-var default."""
    vehicle_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)

    vehicle_repo = FakeVehicleRepo()
    vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    location_repo = FakeVehicleLocationRepo()
    location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    preferences_repo = FakeUserPreferencesRepo()
    notification_preferences_repo = FakeNotificationPreferencesRepo()
    notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True, config={})
    send_notification = FakeSendNotification()
    handler = _make_handler(
        vehicle_repo, location_repo, preferences_repo, notification_preferences_repo, send_notification
    )

    # _NEAR_* (~15m) is under the 50m env default -> no notification.
    handler.handle(
        VehicleLocationUpdated(
            vehicle_id=vehicle_id,
            latitude=_NEAR_LAT,
            longitude=_NEAR_LNG,
            recorded_at=now,
            received_at=now,
            source="push",
        )
    )
    assert send_notification.calls == []

    # _MOVED_* (~1km) is past the 50m env default -> notification sent.
    handler.handle(
        VehicleLocationUpdated(
            vehicle_id=vehicle_id,
            latitude=_MOVED_LAT,
            longitude=_MOVED_LNG,
            recorded_at=now,
            received_at=now,
            source="push",
        )
    )
    assert len(send_notification.calls) == 1


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
    notification_preferences_repo = FakeNotificationPreferencesRepo()
    notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True)
    send_notification = FakeSendNotification()
    handler = _make_handler(
        vehicle_repo, location_repo, preferences_repo, notification_preferences_repo, send_notification
    )

    event = VehicleLocationUpdated(
        vehicle_id=vehicle_id,
        latitude=_MOVED_LAT,
        longitude=_MOVED_LNG,
        recorded_at=now,
        received_at=now,
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
    notification_preferences_repo = FakeNotificationPreferencesRepo()
    notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True)
    send_notification = FakeSendNotification()
    handler = _make_handler(
        vehicle_repo, location_repo, preferences_repo, notification_preferences_repo, send_notification
    )

    event = VehicleLocationUpdated(
        vehicle_id=vehicle_id,
        latitude=_MOVED_LAT,
        longitude=_MOVED_LNG,
        recorded_at=now,
        received_at=now,
        source="push",
    )

    handler.handle(event)

    assert len(send_notification.calls) == 1
    _, message = send_notification.calls[0]
    assert message.text == "Your car with plate 9999ZZZ is now located here."
