"""
Unit tests for SerTicketCreationTriggerHandler's OpenTelemetry instrumentation.

Mirrors test_ser_ticket_notification_trigger_handler_observability.py: each
`handle()` call must produce a root span
(`event_handler.ser_ticket_creation_trigger`); a call whose collaborator
raises must mark that span as an error (with the exception recorded)
WITHOUT the handler's existing swallow-and-continue behavior changing
(handle() must never raise).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from mobility_manager.application.event_handlers.ser_ticket_creation_trigger_handler import (
    SerTicketCreationTriggerHandler,
)
from mobility_manager.domain.entities.user_preferences import UserPreferences
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.domain.value_objects.location import GeoLocation

_LAT, _LNG = 40.4168, -3.7038


class _FakeVehicleRepo:
    def __init__(self, vehicle: Vehicle) -> None:
        self._vehicle = vehicle

    def get_by_id(self, vehicle_id: UUID) -> Vehicle | None:
        return self._vehicle if vehicle_id == self._vehicle.id else None


class _FakeVehicleLocationRepo:
    def get_previous(self, vehicle_id: UUID, before: datetime):
        return None  # first-ever location -> always proceeds to zone check


class _FakeUserPreferencesRepo:
    def __init__(self, user_id: UUID) -> None:
        self._user_id = user_id

    def find_by_user_id(self, user_id: UUID) -> UserPreferences | None:
        return UserPreferences(
            user_id=self._user_id,
            default_ticket_duration_minutes=60,
            auto_create_ticket=True,
            preferred_notification_channel=None,
            notification_language=None,
            timezone=None,
            updated_at=datetime.now(UTC),
        )


class _FakeNotificationPreferencesRepo:
    def find_by_user_id_and_type(self, user_id: UUID, type_key: str):
        return None


class _FakeUserSerProviderConfigRepo:
    def list_connected_providers(self, user_id: UUID) -> list[str]:
        return []  # no provider connected -> creation-failed path, no exception raised


class _FakeFindContainingSerZone:
    def __init__(self, *, raises: bool = False) -> None:
        self._raises = raises

    def execute(self, location: GeoLocation):
        if self._raises:
            raise RuntimeError("zone lookup boom")
        return None


class _FakeDetermineSerTicketRequirement:
    def execute(self, zone, vehicle_id: UUID, at=None) -> bool:
        return False  # no ticket required -> handler returns early


class _FakeCreateSerTicket:
    def execute(self, **kwargs):  # pragma: no cover - not reached in these tests
        raise AssertionError("should not be called")


class _FakeEventPublisher:
    def publish(self, event: object) -> None:
        pass


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


def _make_handler(vehicle_repo, user_id, find_containing_ser_zone) -> SerTicketCreationTriggerHandler:
    return SerTicketCreationTriggerHandler(
        vehicle_repo=vehicle_repo,  # type: ignore[arg-type]
        vehicle_location_repo=_FakeVehicleLocationRepo(),  # type: ignore[arg-type]
        user_preferences_repo=_FakeUserPreferencesRepo(user_id),  # type: ignore[arg-type]
        notification_preferences_repo=_FakeNotificationPreferencesRepo(),  # type: ignore[arg-type]
        user_ser_provider_config_repo=_FakeUserSerProviderConfigRepo(),  # type: ignore[arg-type]
        find_containing_ser_zone=find_containing_ser_zone,  # type: ignore[arg-type]
        determine_ser_ticket_requirement=_FakeDetermineSerTicketRequirement(),  # type: ignore[arg-type]
        create_ser_ticket=_FakeCreateSerTicket(),  # type: ignore[arg-type]
        event_publisher=_FakeEventPublisher(),  # type: ignore[arg-type]
    )


def test_successful_handle_produces_a_span_with_no_error(
    otel_span_exporter: InMemorySpanExporter,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS", "50")
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    vehicle = _make_vehicle(vehicle_id, user_id)
    handler = _make_handler(_FakeVehicleRepo(vehicle), user_id, _FakeFindContainingSerZone())

    handler.handle(_make_event(vehicle_id, now))

    spans = otel_span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "event_handler.ser_ticket_creation_trigger"
    assert spans[0].status.status_code == StatusCode.UNSET


def test_failed_zone_lookup_marks_span_as_error_without_raising(
    otel_span_exporter: InMemorySpanExporter,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS", "50")
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    vehicle = _make_vehicle(vehicle_id, user_id)
    handler = _make_handler(_FakeVehicleRepo(vehicle), user_id, _FakeFindContainingSerZone(raises=True))

    result = handler.handle(_make_event(vehicle_id, now))  # must not raise

    assert result is None
    spans = otel_span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].status.status_code == StatusCode.ERROR
    assert any(event.name == "exception" for event in spans[0].events)
