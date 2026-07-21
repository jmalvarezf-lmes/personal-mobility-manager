"""
Unit tests for NotificationDispatchHandler's OpenTelemetry instrumentation.

Each `handle()` call must produce a root span
(`event_handler.notification_dispatch`); a call whose collaborator raises
must mark that span as an error (with the exception recorded) WITHOUT the
handler's existing swallow-and-continue behavior changing (handle() must
never raise). Every actual send_notification attempt must also record a
`record_notification_dispatch` metric labeled by channel and outcome.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

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
from mobility_manager.domain.exceptions import NotificationChannelApiError
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.domain.value_objects.notification_message import (
    NotificationMessage,
)

_FAR_LAT, _FAR_LNG = 40.4168, -3.7038
_MOVED_LAT, _MOVED_LNG = 40.4258, -3.7038  # ~1km north — comfortably past the default 50m threshold

_TYPE_KEY = "location_moved"


class _FakeVehicleRepo:
    def __init__(self, vehicle: Vehicle) -> None:
        self._vehicle = vehicle

    def get_by_id(self, vehicle_id: UUID) -> Vehicle | None:
        return self._vehicle if vehicle_id == self._vehicle.id else None


class _FakeVehicleLocationRepo:
    def __init__(self, previous: VehicleLocation | None) -> None:
        self._previous = previous

    def get_previous(self, vehicle_id: UUID, before: datetime) -> VehicleLocation | None:
        return self._previous


class _FakeUserPreferencesRepo:
    def __init__(self, preferences: UserPreferences | None) -> None:
        self._preferences = preferences

    def find_by_user_id(self, user_id: UUID) -> UserPreferences | None:
        return self._preferences


class _FakeNotificationPreferencesRepo:
    def __init__(self, preference: UserNotificationPreference | None) -> None:
        self._preference = preference

    def find_by_user_id_and_type(self, user_id: UUID, type_key: str) -> UserNotificationPreference | None:
        return self._preference


class _FakeSendNotification:
    def __init__(self, *, raises: bool = False, result: bool = True) -> None:
        self._raises = raises
        self._result = result
        self.calls: list[tuple[UUID, NotificationMessage]] = []

    def execute(self, user_id: UUID, message: NotificationMessage) -> bool:
        self.calls.append((user_id, message))
        if self._raises:
            raise NotificationChannelApiError("telegram send failed")
        return self._result


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


def _make_previous_location(vehicle_id: UUID, now: datetime) -> VehicleLocation:
    return VehicleLocation(
        id=uuid4(),
        vehicle_id=vehicle_id,
        latitude=_FAR_LAT,
        longitude=_FAR_LNG,
        recorded_at=now,
        received_at=now,
        source="push",
    )


def _make_event(vehicle_id: UUID, now: datetime) -> VehicleLocationUpdated:
    return VehicleLocationUpdated(
        vehicle_id=vehicle_id,
        latitude=_MOVED_LAT,
        longitude=_MOVED_LNG,
        recorded_at=now,
        received_at=now,
        source="push",
    )


def test_successful_dispatch_produces_a_span_and_records_metric(
    otel_span_exporter: InMemorySpanExporter,
    otel_metric_reader: InMemoryMetricReader,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS", "50")
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    vehicle = _make_vehicle(vehicle_id, user_id)
    preferences = UserPreferences(
        user_id=user_id,
        default_ticket_duration_minutes=60,
        auto_create_ticket=False,
        preferred_notification_channel="telegram",
        notification_language=None,
        timezone=None,
        updated_at=now,
    )
    notification_preference = UserNotificationPreference(
        user_id=user_id, type_key=_TYPE_KEY, enabled=True, config={}, updated_at=now
    )
    send_notification = _FakeSendNotification(result=True)

    handler = NotificationDispatchHandler(
        vehicle_repo=_FakeVehicleRepo(vehicle),  # type: ignore[arg-type]
        vehicle_location_repo=_FakeVehicleLocationRepo(_make_previous_location(vehicle_id, now)),  # type: ignore[arg-type]
        user_preferences_repo=_FakeUserPreferencesRepo(preferences),  # type: ignore[arg-type]
        notification_preferences_repo=_FakeNotificationPreferencesRepo(notification_preference),  # type: ignore[arg-type]
        send_notification=send_notification,  # type: ignore[arg-type]
    )

    metric_attrs = {"channel": "telegram", "success": True}
    data = otel_metric_reader.get_metrics_data()
    before = 0
    if data is not None:
        for rm in data.resource_metrics:
            for sm in rm.scope_metrics:
                for metric in sm.metrics:
                    if metric.name != "mobility_manager.notification_dispatch":
                        continue
                    for point in metric.data.data_points:
                        if dict(point.attributes) == metric_attrs:
                            before = int(point.value)

    handler.handle(_make_event(vehicle_id, now))

    assert len(send_notification.calls) == 1
    spans = otel_span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "event_handler.notification_dispatch"
    assert spans[0].status.status_code == StatusCode.UNSET

    data = otel_metric_reader.get_metrics_data()
    after = 0
    assert data is not None
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for metric in sm.metrics:
                if metric.name != "mobility_manager.notification_dispatch":
                    continue
                for point in metric.data.data_points:
                    if dict(point.attributes) == metric_attrs:
                        after = int(point.value)
    assert after == before + 1


def test_failed_send_marks_span_as_error_without_raising(
    otel_span_exporter: InMemorySpanExporter,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS", "50")
    vehicle_id, user_id, now = uuid4(), uuid4(), datetime.now(UTC)
    vehicle = _make_vehicle(vehicle_id, user_id)
    preferences = UserPreferences(
        user_id=user_id,
        default_ticket_duration_minutes=60,
        auto_create_ticket=False,
        preferred_notification_channel="telegram",
        notification_language=None,
        timezone=None,
        updated_at=now,
    )
    notification_preference = UserNotificationPreference(
        user_id=user_id, type_key=_TYPE_KEY, enabled=True, config={}, updated_at=now
    )
    send_notification = _FakeSendNotification(raises=True)

    handler = NotificationDispatchHandler(
        vehicle_repo=_FakeVehicleRepo(vehicle),  # type: ignore[arg-type]
        vehicle_location_repo=_FakeVehicleLocationRepo(_make_previous_location(vehicle_id, now)),  # type: ignore[arg-type]
        user_preferences_repo=_FakeUserPreferencesRepo(preferences),  # type: ignore[arg-type]
        notification_preferences_repo=_FakeNotificationPreferencesRepo(notification_preference),  # type: ignore[arg-type]
        send_notification=send_notification,  # type: ignore[arg-type]
    )

    result = handler.handle(_make_event(vehicle_id, now))  # must not raise

    assert result is None
    spans = otel_span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].status.status_code == StatusCode.ERROR
    assert any(event.name == "exception" for event in spans[0].events)


def test_skip_path_still_produces_a_span_with_no_error(
    otel_span_exporter: InMemorySpanExporter,
) -> None:
    """A missing vehicle skips silently — still produces a span, but never marks it as an error."""
    vehicle_id, now = uuid4(), datetime.now(UTC)
    handler = NotificationDispatchHandler(
        vehicle_repo=_FakeVehicleRepo(_make_vehicle(uuid4(), uuid4())),  # type: ignore[arg-type] # different vehicle id -> not found
        vehicle_location_repo=_FakeVehicleLocationRepo(None),  # type: ignore[arg-type]
        user_preferences_repo=_FakeUserPreferencesRepo(None),  # type: ignore[arg-type]
        notification_preferences_repo=_FakeNotificationPreferencesRepo(None),  # type: ignore[arg-type]
        send_notification=_FakeSendNotification(),  # type: ignore[arg-type]
    )

    handler.handle(_make_event(vehicle_id, now))

    spans = otel_span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].status.status_code == StatusCode.UNSET
