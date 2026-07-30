"""
Unit tests for SerTicketNotificationTriggerHandler's OpenTelemetry instrumentation.

Each `on_vehicle_location_updated()` call must produce a root span
(`event_handler.ser_ticket_notification.on_vehicle_location_updated`); a
call whose collaborator raises must mark that span as an error (with the
exception recorded) WITHOUT the handler's existing swallow-and-continue
behavior changing (the method must never raise). No dedicated custom metric
is recorded for this handler.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from mobility_manager.application.event_handlers.ser_ticket_notification_trigger_handler import (
    SerTicketNotificationTriggerHandler,
)
from mobility_manager.application.use_cases.ser_zone_recheck_gate import (
    SerZoneRecheckDecision,
)
from mobility_manager.domain.entities.user_notification_preference import (
    UserNotificationPreference,
)
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)
from mobility_manager.domain.value_objects.brand import Brand

_LAT, _LNG = 40.4168, -3.7038

_TYPE_KEY = "ser_zone_ticket_required"


class _FakeVehicleRepo:
    def __init__(self, vehicle: Vehicle) -> None:
        self._vehicle = vehicle

    def get_by_id(self, vehicle_id: UUID) -> Vehicle | None:
        return self._vehicle if vehicle_id == self._vehicle.id else None


class _FakeSerZoneRecheckGate:
    def __init__(self, *, raises: bool = False) -> None:
        self._raises = raises

    def evaluate(self, event: VehicleLocationUpdated, movement_floor_meters: float) -> SerZoneRecheckDecision:
        if self._raises:
            raise RuntimeError("zone lookup boom")
        return SerZoneRecheckDecision(should_check=True, zone=None)


class _FakeNotificationPreferencesRepo:
    def __init__(self, preference: UserNotificationPreference | None) -> None:
        self._preference = preference

    def find_by_user_id_and_type(self, user_id: UUID, type_key: str) -> UserNotificationPreference | None:
        return self._preference


class _FakeUserPreferencesRepo:
    def find_by_user_id(self, user_id: UUID):
        return None


class _FakeDetermineSerTicketRequirement:
    def execute(self, zone, vehicle_id: UUID, at=None) -> bool:
        return False  # no ticket required -> handler returns early, no notification needed


class _FakeSendNotification:
    def execute(self, user_id: UUID, message) -> bool:  # pragma: no cover - not reached in these tests
        return True


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


def _make_event(vehicle_id: UUID, now: datetime) -> VehicleLocationUpdated:
    return VehicleLocationUpdated(
        vehicle_id=vehicle_id,
        latitude=_LAT,
        longitude=_LNG,
        recorded_at=now,
        received_at=now,
        source="push",
    )


def _make_handler(vehicle_repo, ser_zone_recheck_gate) -> SerTicketNotificationTriggerHandler:
    return SerTicketNotificationTriggerHandler(
        vehicle_repo=vehicle_repo,  # type: ignore[arg-type]
        user_preferences_repo=_FakeUserPreferencesRepo(),  # type: ignore[arg-type]
        notification_preferences_repo=_FakeNotificationPreferencesRepo(
            UserNotificationPreference(
                user_id=uuid4(), type_key=_TYPE_KEY, enabled=True, config={}, updated_at=datetime.now(UTC)
            )
        ),  # type: ignore[arg-type]
        determine_ser_ticket_requirement=_FakeDetermineSerTicketRequirement(),  # type: ignore[arg-type]
        ser_zone_recheck_gate=ser_zone_recheck_gate,  # type: ignore[arg-type]
        send_notification=_FakeSendNotification(),  # type: ignore[arg-type]
    )


def test_successful_handle_produces_a_span_with_no_error(
    otel_span_exporter: InMemorySpanExporter,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS", "50")
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    vehicle = _make_vehicle(vehicle_id, user_id)
    handler = _make_handler(_FakeVehicleRepo(vehicle), _FakeSerZoneRecheckGate())

    handler.on_vehicle_location_updated(_make_event(vehicle_id, now))

    spans = otel_span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "event_handler.ser_ticket_notification.on_vehicle_location_updated"
    assert spans[0].status.status_code == StatusCode.UNSET


def test_failed_zone_lookup_marks_span_as_error_without_raising(
    otel_span_exporter: InMemorySpanExporter,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS", "50")
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    vehicle = _make_vehicle(vehicle_id, user_id)
    handler = _make_handler(_FakeVehicleRepo(vehicle), _FakeSerZoneRecheckGate(raises=True))

    result = handler.on_vehicle_location_updated(_make_event(vehicle_id, now))  # must not raise

    assert result is None
    spans = otel_span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].status.status_code == StatusCode.ERROR
    assert any(event.name == "exception" for event in spans[0].events)
