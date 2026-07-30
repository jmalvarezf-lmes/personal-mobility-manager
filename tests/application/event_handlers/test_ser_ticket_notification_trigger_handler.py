"""
Unit tests for SerTicketNotificationTriggerHandler.

Covers every scenario in the ser-zone-ticket-notification and
vehicle-location-events specs: a disabled (or missing) `ser_zone_ticket_required`
preference skips before ever calling `SerZoneRecheckGate.evaluate`, the gate
signalling `should_check=False` skips without calling
`DetermineSerTicketRequirement`, a stationary vehicle with no active ticket
still gets rechecked (delegated to the gate), the newly-gained
zone-unchanged skip (delegated to the gate, with an active ticket), no
notification when `DetermineSerTicketRequirement` returns False, a
notification with the correct plate/zone_number when it returns True, a
missing vehicle is skipped without error, the effective threshold passed to
the gate is independent from `location_moved`'s, the message is localized to
the owner's `notification_language` (or falls back to the default when
unset), and the early exit when the owner's `auto_create_ticket` is enabled.
Also confirms no ticket-provider or ticket-creation code path is ever
exercised.

The previous-location/distance/zone-comparison logic itself now lives in
SerZoneRecheckGate (see change-ser-ticket-stationary-recheck design.md
D3/D4/D5) and is unit-tested there (test_ser_zone_recheck_gate.py) — this
handler is tested here against a mocked gate.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from shapely.geometry import Polygon

from mobility_manager.application.event_handlers.ser_ticket_notification_trigger_handler import (
    SerTicketNotificationTriggerHandler,
)
from mobility_manager.application.use_cases.ser_zone_recheck_gate import (
    SerZoneRecheckDecision,
)
from mobility_manager.config import resolve_effective_threshold
from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.entities.user_notification_preference import (
    UserNotificationPreference,
)
from mobility_manager.domain.entities.user_preferences import UserPreferences
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.domain.value_objects.notification_message import (
    NotificationMessage,
)

_MOVED_LAT, _MOVED_LNG = 40.4258, -3.7038

_SQUARE = Polygon([(440584, 4474459), (440604, 4474459), (440604, 4474479), (440584, 4474479)])

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
        self.find_by_user_id_and_type_calls: list[tuple[UUID, str]] = []

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
        self.find_by_user_id_and_type_calls.append((user_id, type_key))
        return self._rows.get((user_id, type_key))

    def update(self, user_id, type_key, enabled, config):  # pragma: no cover - not exercised by this handler
        raise NotImplementedError


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


def _make_ser_zone(zone_number: str = "163") -> SerZone:
    return SerZone(
        city_code="madrid",
        zone_number=zone_number,
        zone_type="Azul",
        district="CENTRO",
        spot_count=15,
        geometry=_SQUARE,
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
        self.notification_preferences_repo = FakeNotificationPreferencesRepo()
        self.determine_requirement = FakeDetermineSerTicketRequirement(required=True)
        self.ser_zone_recheck_gate = FakeSerZoneRecheckGate()
        self.send_notification = FakeSendNotification()

    def build(self) -> SerTicketNotificationTriggerHandler:
        return SerTicketNotificationTriggerHandler(
            vehicle_repo=self.vehicle_repo,  # type: ignore[arg-type]
            user_preferences_repo=self.preferences_repo,  # type: ignore[arg-type]
            notification_preferences_repo=self.notification_preferences_repo,  # type: ignore[arg-type]
            determine_ser_ticket_requirement=self.determine_requirement,  # type: ignore[arg-type]
            ser_zone_recheck_gate=self.ser_zone_recheck_gate,  # type: ignore[arg-type]
            send_notification=self.send_notification,  # type: ignore[arg-type]
        )


def test_skips_entirely_when_auto_create_ticket_is_enabled() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.preferences_repo.set(user_id, None, auto_create_ticket=True)
    fx.notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True)
    handler = fx.build()

    handler.on_vehicle_location_updated(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert fx.send_notification.calls == []
    assert fx.notification_preferences_repo.find_by_user_id_and_type_calls == []
    assert fx.ser_zone_recheck_gate.calls == []


def test_disabled_preference_skips_before_calling_recheck_gate() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=False)
    handler = fx.build()

    handler.on_vehicle_location_updated(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert fx.ser_zone_recheck_gate.calls == []
    assert fx.determine_requirement.calls == []
    assert fx.send_notification.calls == []


def test_missing_preference_row_skips_before_calling_recheck_gate() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    # no notification preference row at all
    handler = fx.build()

    handler.on_vehicle_location_updated(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert fx.ser_zone_recheck_gate.calls == []
    assert fx.send_notification.calls == []


def test_ser_zone_recheck_gate_signals_no_check_needed() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True)
    fx.ser_zone_recheck_gate.decision = SerZoneRecheckDecision(should_check=False, zone=None)
    handler = fx.build()

    handler.on_vehicle_location_updated(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert fx.determine_requirement.calls == []
    assert fx.send_notification.calls == []


def test_zone_unchanged_with_active_ticket_skips_via_gate() -> None:
    """
    The zone-unchanged skip (only valid while the vehicle holds an active
    ParkingTicket — see design.md D5) is now the gate's own responsibility;
    from the handler's perspective this is just should_check=False.
    """
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True)
    fx.ser_zone_recheck_gate.decision = SerZoneRecheckDecision(should_check=False, zone=None)
    handler = fx.build()

    handler.on_vehicle_location_updated(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert fx.determine_requirement.calls == []
    assert fx.send_notification.calls == []


def test_stationary_vehicle_with_no_active_ticket_still_gets_rechecked() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True)
    zone = _make_ser_zone(zone_number="163")
    fx.ser_zone_recheck_gate.decision = SerZoneRecheckDecision(should_check=True, zone=zone)
    fx.determine_requirement.required = False
    handler = fx.build()

    handler.on_vehicle_location_updated(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert fx.determine_requirement.calls == [(zone, vehicle_id)]
    assert fx.send_notification.calls == []


def test_skips_notification_when_ticket_not_required() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True)
    fx.ser_zone_recheck_gate.decision = SerZoneRecheckDecision(should_check=True, zone=None)
    fx.determine_requirement.required = False
    handler = fx.build()

    handler.on_vehicle_location_updated(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert fx.send_notification.calls == []


def test_determine_ser_ticket_requirement_is_called_with_vehicle_id() -> None:
    """
    DetermineSerTicketRequirement must be called with event.vehicle_id so a
    matching per-vehicle exemption can suppress the requirement (see
    vehicle-ser-parking-exemption spec.md).
    """
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True)
    zone = _make_ser_zone(zone_number="163")
    fx.ser_zone_recheck_gate.decision = SerZoneRecheckDecision(should_check=True, zone=zone)
    fx.determine_requirement.required = False
    handler = fx.build()

    handler.on_vehicle_location_updated(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert fx.determine_requirement.calls == [(zone, vehicle_id)]


def test_matching_vehicle_exemption_suppresses_notification() -> None:
    """
    When DetermineSerTicketRequirement returns False because of a matching
    exemption, this handler must behave exactly like any other "no ticket
    required" outcome — no notification.
    """
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True)
    fx.ser_zone_recheck_gate.decision = SerZoneRecheckDecision(
        should_check=True, zone=_make_ser_zone(zone_number="163")
    )
    # A matching exemption means DetermineSerTicketRequirement itself
    # returns False — this handler doesn't need to know why.
    fx.determine_requirement.required = False
    handler = fx.build()

    handler.on_vehicle_location_updated(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert fx.send_notification.calls == []


def test_sends_notification_with_correct_plate_and_zone_number() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id, license_plate="1234ABC"))
    fx.preferences_repo.set(user_id, None)
    fx.notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True)
    fx.ser_zone_recheck_gate.decision = SerZoneRecheckDecision(
        should_check=True, zone=_make_ser_zone(zone_number="163")
    )
    fx.determine_requirement.required = True
    handler = fx.build()

    handler.on_vehicle_location_updated(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert len(fx.send_notification.calls) == 1
    called_user_id, message = fx.send_notification.calls[0]
    assert called_user_id == user_id
    assert "1234ABC" in message.text
    assert "163" in message.text
    assert message.location is not None
    assert message.location.lat == _MOVED_LAT
    assert message.location.lng == _MOVED_LNG


def test_no_notification_when_ticket_required_but_zone_is_none() -> None:
    """
    Defensive branch: if DetermineSerTicketRequirement ever returned True for
    a None zone, the handler must not proceed to build a notification that
    needs zone.zone_number (would raise AttributeError) — it returns instead.
    """
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True)
    fx.ser_zone_recheck_gate.decision = SerZoneRecheckDecision(should_check=True, zone=None)
    fx.determine_requirement.required = True
    handler = fx.build()

    handler.on_vehicle_location_updated(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert fx.send_notification.calls == []


def test_missing_vehicle_is_skipped_without_error() -> None:
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()  # no vehicle registered
    handler = fx.build()

    result = handler.on_vehicle_location_updated(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert result is None
    assert fx.ser_zone_recheck_gate.calls == []
    assert fx.determine_requirement.calls == []
    assert fx.send_notification.calls == []


def test_effective_threshold_passed_to_gate_is_independent_from_location_moved() -> None:
    """
    Configuring a different threshold_m for ser_zone_ticket_required than
    location_moved must not cross-talk: this handler only ever reads its
    own (user_id, "ser_zone_ticket_required") row's config to compute the
    movement_floor_meters it passes to SerZoneRecheckGate.evaluate, never
    "location_moved"'s.
    """
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    # location_moved has a huge threshold; ser_zone_ticket_required has a tiny one.
    fx.notification_preferences_repo.set(user_id, "location_moved", enabled=True, config={"threshold_m": 100_000})
    fx.notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True, config={"threshold_m": 5})
    handler = fx.build()

    handler.on_vehicle_location_updated(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert len(fx.ser_zone_recheck_gate.calls) == 1
    _event, floor = fx.ser_zone_recheck_gate.calls[0]
    assert floor == 5


def test_effective_threshold_falls_back_to_default_when_config_unset() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id))
    fx.notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True, config={})
    handler = fx.build()

    handler.on_vehicle_location_updated(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert len(fx.ser_zone_recheck_gate.calls) == 1
    _event, floor = fx.ser_zone_recheck_gate.calls[0]
    assert floor == resolve_effective_threshold({})


def test_message_localized_to_owner_notification_language() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id, license_plate="9999ZZZ"))
    fx.preferences_repo.set(user_id, "es")
    fx.notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True)
    fx.ser_zone_recheck_gate.decision = SerZoneRecheckDecision(
        should_check=True, zone=_make_ser_zone(zone_number="163")
    )
    fx.determine_requirement.required = True
    handler = fx.build()

    handler.on_vehicle_location_updated(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert len(fx.send_notification.calls) == 1
    _, message = fx.send_notification.calls[0]
    assert message.text == (
        "Tu coche con matrícula 9999ZZZ está en la zona SER 163 — necesitas crear un tique de estacionamiento."
    )


def test_message_falls_back_to_default_language_when_unset() -> None:
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.vehicle_repo.add(_make_vehicle(vehicle_id, user_id, license_plate="9999ZZZ"))
    # no preferences row at all
    fx.notification_preferences_repo.set(user_id, _TYPE_KEY, enabled=True)
    fx.ser_zone_recheck_gate.decision = SerZoneRecheckDecision(
        should_check=True, zone=_make_ser_zone(zone_number="163")
    )
    fx.determine_requirement.required = True
    handler = fx.build()

    handler.on_vehicle_location_updated(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now))

    assert len(fx.send_notification.calls) == 1
    _, message = fx.send_notification.calls[0]
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

    params = inspect.signature(SerTicketNotificationTriggerHandler.__init__).parameters
    assert "ser_ticket_provider" not in params
    assert "create_ser_ticket" not in params
