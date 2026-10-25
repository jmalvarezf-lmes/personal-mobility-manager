"""
Unit tests for SerTicketNotificationTriggerHandler.

Covers every scenario in the ser-zone-ticket-notification modified spec:
activation-event-driven notification to owner and sharees, preference gating,
owner auto_create_ticket suppression, localization, and audit recording.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from mobility_manager.application.event_handlers.ser_ticket_notification_trigger_handler import (
    SerTicketNotificationTriggerHandler,
)
from mobility_manager.domain.entities.user_notification_preference import (
    UserNotificationPreference,
)
from mobility_manager.domain.entities.user_preferences import UserPreferences
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.entities.vehicle_share import VehicleShare
from mobility_manager.domain.events.ser_ticket_requirement_activated import (
    SerTicketRequirementActivated,
)
from mobility_manager.domain.ports.user_ser_requirement_notification_repository import (
    UserSerRequirementNotification,
)
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.domain.value_objects.notification_message import (
    NotificationMessage,
)

_MOVED_LAT, _MOVED_LNG = 40.4258, -3.7038

_TYPE_KEY = "ser_zone_ticket_required"


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

    def set(
        self,
        user_id: UUID,
        notification_language: str | None,
        auto_create_ticket: bool = False,
    ) -> None:
        self.preferences[user_id] = UserPreferences(
            user_id=user_id,
            default_ticket_duration_minutes=60,
            auto_create_ticket=auto_create_ticket,
            preferred_notification_channel="telegram",
            notification_language=notification_language,
            timezone=None,
            updated_at=datetime.now(UTC),
        )

    def find_by_user_id(self, user_id: UUID) -> UserPreferences | None:
        return self.preferences.get(user_id)


class FakeNotificationPreferencesRepo:
    def __init__(self) -> None:
        self._rows: dict[tuple[UUID, str], UserNotificationPreference] = {}

    def set(self, user_id: UUID, type_key: str, enabled: bool, config: dict | None = None) -> None:
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


class FakeVehicleShareRepo:
    def __init__(self) -> None:
        self.shares: list[VehicleShare] = []

    def save(self, share: VehicleShare) -> None:
        self.shares.append(share)

    def find_by_vehicle_and_user(self, vehicle_id: UUID, user_id: UUID) -> VehicleShare | None:
        return next(
            (s for s in self.shares if s.vehicle_id == vehicle_id and s.user_id == user_id),
            None,
        )

    def list_sharees(self, vehicle_id: UUID) -> list[VehicleShare]:
        return [s for s in self.shares if s.vehicle_id == vehicle_id]

    def delete(self, vehicle_id: UUID, user_id: UUID) -> None:
        self.shares = [s for s in self.shares if not (s.vehicle_id == vehicle_id and s.user_id == user_id)]

    def list_vehicle_ids_for_user(self, user_id: UUID) -> list[UUID]:
        return [s.vehicle_id for s in self.shares if s.user_id == user_id]


class FakeNotificationAuditRepo:
    def __init__(self) -> None:
        self.saved: list[UserSerRequirementNotification] = []
        self.fail_next = False

    def save(self, notification: UserSerRequirementNotification) -> None:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("audit write failed")
        self.saved.append(notification)


def _make_vehicle(vehicle_id: UUID, user_id: UUID, license_plate: str | None = "1234ABC") -> Vehicle:
    return Vehicle(
        id=vehicle_id,
        brand=Brand.GENERIC,
        display_name="Test Vehicle",
        vin=None,
        license_plate=license_plate,
        created_at=datetime.now(UTC),
        owner_id=user_id,
    )


def _make_event(
    vehicle_id: UUID,
    city_code: str | None = "madrid",
    zone_number: str | None = "163",
    lat: float = _MOVED_LAT,
    lng: float = _MOVED_LNG,
    activated_at: datetime | None = None,
) -> SerTicketRequirementActivated:
    return SerTicketRequirementActivated(
        vehicle_id=vehicle_id,
        city_code=city_code,
        zone_number=zone_number,
        latitude=lat,
        longitude=lng,
        activated_at=activated_at or datetime.now(UTC),
    )


class _Fixture:
    def __init__(self) -> None:
        self.vehicle_repo = FakeVehicleRepo()
        self.preferences_repo = FakeUserPreferencesRepo()
        self.notification_preferences_repo = FakeNotificationPreferencesRepo()
        self.send_notification = FakeSendNotification()
        self.share_repo = FakeVehicleShareRepo()
        self.notification_audit_repo = FakeNotificationAuditRepo()

    def build(self) -> SerTicketNotificationTriggerHandler:
        return SerTicketNotificationTriggerHandler(
            vehicle_repo=self.vehicle_repo,  # type: ignore[arg-type]
            user_preferences_repo=self.preferences_repo,  # type: ignore[arg-type]
            notification_preferences_repo=self.notification_preferences_repo,  # type: ignore[arg-type]
            vehicle_share_repo=self.share_repo,  # type: ignore[arg-type]
            send_notification=self.send_notification,  # type: ignore[arg-type]
            notification_audit_repo=self.notification_audit_repo,  # type: ignore[arg-type]
        )


def test_skips_entirely_when_auto_create_ticket_is_enabled() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.preferences_repo.set(user_id, None, auto_create_ticket=True)
    fx.notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True)
    handler = fx.build()

    handler.on_requirement_activated(_make_event(vehicle_id, activated_at=now))

    assert fx.send_notification.calls == []
    assert fx.notification_audit_repo.saved == []


def test_disabled_preference_skips_recipient() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=False)
    handler = fx.build()

    handler.on_requirement_activated(_make_event(vehicle_id, activated_at=now))

    assert fx.send_notification.calls == []
    assert fx.notification_audit_repo.saved == []


def test_missing_preference_row_skips_recipient() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    # no notification preference row at all
    handler = fx.build()

    handler.on_requirement_activated(_make_event(vehicle_id, activated_at=now))

    assert fx.send_notification.calls == []
    assert fx.notification_audit_repo.saved == []


def test_sends_notification_with_correct_plate_and_zone_number() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id, license_plate="1234ABC"))
    fx.preferences_repo.set(user_id, None)
    fx.notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True)
    handler = fx.build()

    handler.on_requirement_activated(_make_event(vehicle_id, activated_at=now))

    assert len(fx.send_notification.calls) == 1
    called_user_id, message = fx.send_notification.calls[0]
    assert called_user_id == user_id
    assert "1234ABC" in message.text
    assert "163" in message.text
    assert message.location is not None
    assert message.location.lat == _MOVED_LAT
    assert message.location.lng == _MOVED_LNG

    assert len(fx.notification_audit_repo.saved) == 1
    audit = fx.notification_audit_repo.saved[0]
    assert audit.user_id == user_id
    assert audit.vehicle_id == vehicle_id
    assert audit.city_code == "madrid"
    assert audit.zone_number == "163"
    assert audit.latitude == _MOVED_LAT
    assert audit.longitude == _MOVED_LNG
    assert audit.requirement_activated_at == now


def test_missing_vehicle_is_skipped_without_error() -> None:
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()  # no vehicle registered
    handler = fx.build()

    result = handler.on_requirement_activated(_make_event(vehicle_id, activated_at=now))

    assert result is None
    assert fx.send_notification.calls == []
    assert fx.notification_audit_repo.saved == []


def test_message_localized_to_owner_notification_language() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id, license_plate="9999ZZZ"))
    fx.preferences_repo.set(user_id, "es")
    fx.notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True)
    handler = fx.build()

    handler.on_requirement_activated(_make_event(vehicle_id, activated_at=now))

    assert len(fx.send_notification.calls) == 1
    _, message = fx.send_notification.calls[0]
    assert message.text == (
        "Tu coche con matrícula 9999ZZZ está en la zona SER 163 — necesitas crear un tique de estacionamiento."
    )


def test_message_falls_back_to_default_language_when_unset() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id, license_plate="9999ZZZ"))
    fx.notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True)
    handler = fx.build()

    handler.on_requirement_activated(_make_event(vehicle_id, activated_at=now))

    assert len(fx.send_notification.calls) == 1
    _, message = fx.send_notification.calls[0]
    assert message.text == "Your car with plate 9999ZZZ is in SER zone 163 — you need to create a parking ticket."


def test_owner_and_sharee_both_receive_notification_when_enabled() -> None:
    vehicle_id, owner_id, sharee_id, now = uuid4(), uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, owner_id))
    fx.preferences_repo.set(owner_id, None)
    fx.preferences_repo.set(sharee_id, None)
    fx.notification_preferences_repo.set(owner_id, _TYPE_KEY, enabled=True)
    fx.notification_preferences_repo.set(sharee_id, _TYPE_KEY, enabled=True)
    fx.share_repo.save(
        VehicleShare(
            vehicle_id=vehicle_id,
            user_id=sharee_id,
            created_at=datetime.now(UTC),
        )
    )
    handler = fx.build()

    handler.on_requirement_activated(_make_event(vehicle_id, activated_at=now))

    notified_user_ids = {uid for uid, _ in fx.send_notification.calls}
    assert notified_user_ids == {owner_id, sharee_id}
    assert len(fx.notification_audit_repo.saved) == 2


def test_sharee_does_not_receive_notification_when_preference_disabled() -> None:
    vehicle_id, owner_id, sharee_id, now = uuid4(), uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, owner_id))
    fx.preferences_repo.set(owner_id, None)
    fx.preferences_repo.set(sharee_id, None)
    fx.notification_preferences_repo.set(owner_id, _TYPE_KEY, enabled=True)
    fx.notification_preferences_repo.set(sharee_id, _TYPE_KEY, enabled=False)
    fx.share_repo.save(
        VehicleShare(
            vehicle_id=vehicle_id,
            user_id=sharee_id,
            created_at=datetime.now(UTC),
        )
    )
    handler = fx.build()

    handler.on_requirement_activated(_make_event(vehicle_id, activated_at=now))

    notified_user_ids = {uid for uid, _ in fx.send_notification.calls}
    assert notified_user_ids == {owner_id}


def test_owners_auto_create_ticket_suppresses_only_owner_path() -> None:
    vehicle_id, owner_id, sharee_id, now = uuid4(), uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, owner_id))
    fx.preferences_repo.set(owner_id, None, auto_create_ticket=True)
    fx.preferences_repo.set(sharee_id, None)
    fx.notification_preferences_repo.set(owner_id, _TYPE_KEY, enabled=True)
    fx.notification_preferences_repo.set(sharee_id, _TYPE_KEY, enabled=True)
    fx.share_repo.save(
        VehicleShare(
            vehicle_id=vehicle_id,
            user_id=sharee_id,
            created_at=datetime.now(UTC),
        )
    )
    handler = fx.build()

    handler.on_requirement_activated(_make_event(vehicle_id, activated_at=now))

    notified_user_ids = {uid for uid, _ in fx.send_notification.calls}
    assert notified_user_ids == {sharee_id}


def test_no_notification_when_zone_number_is_none() -> None:
    """
    Defensive branch: if an activation event ever carries zone_number=None,
    the handler must not build a notification that needs zone_number.
    """
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True)
    handler = fx.build()

    handler.on_requirement_activated(_make_event(vehicle_id, zone_number=None, activated_at=now))

    assert fx.send_notification.calls == []
    assert fx.notification_audit_repo.saved == []


def test_audit_failure_does_not_block_notification() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True)
    fx.notification_audit_repo.fail_next = True
    handler = fx.build()

    handler.on_requirement_activated(_make_event(vehicle_id, activated_at=now))

    assert len(fx.send_notification.calls) == 1
    assert fx.notification_audit_repo.saved == []


def test_no_ticket_provider_or_ticket_creation_code_path_is_exercised() -> None:
    """
    Guards the non-goal explicitly: this handler must never touch a
    SerTicketProvider or any ticket-creation use case, regardless of
    outcome. There is no such dependency injected into the handler at all,
    so this test asserts the constructor's dependency set stays exactly as
    scoped (no provider/create-ticket collaborator sneaks in).
    """
    import inspect

    params = inspect.signature(SerTicketNotificationTriggerHandler.__init__).parameters
    assert "ser_ticket_provider" not in params
    assert "create_ser_ticket" not in params
