"""
Unit tests for VehicleLocationScheduler's OpenTelemetry instrumentation.

Each per-vehicle poll must produce a root span
(`scheduler.vehicle_location.poll`), and a poll whose collaborator raises
must mark that span as an error (with the exception recorded) WITHOUT the
scheduler's existing per-vehicle swallow-and-continue behavior changing —
i.e. remaining vehicles must still be polled after one fails.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.entities.vehicle_location import VehicleLocation
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.domain.value_objects.toyota_config import ToyotaConfig
from mobility_manager.infrastructure.vehicle_location_scheduler import (
    VehicleLocationScheduler,
)


class _FakeVehicleRepo:
    def __init__(self, vehicles: list[Vehicle]) -> None:
        self._vehicles = vehicles

    def get_all_by_brand(self, brand: Brand) -> list[Vehicle]:
        return self._vehicles


class _FakeConfigRepo:
    def get_toyota_config(self, vehicle_id: UUID) -> ToyotaConfig:
        return ToyotaConfig(username="u", password="p", locale="en_GB", vin="VIN123")


class _FakeLocationProvider:
    def __init__(self, *, raises: bool = False, location: VehicleLocation | None = None) -> None:
        self._raises = raises
        self._location = location
        self.calls: list[UUID] = []

    def fetch_location(self, vehicle_id: UUID, config: ToyotaConfig) -> VehicleLocation | None:
        self.calls.append(vehicle_id)
        if self._raises:
            raise RuntimeError("toyota api boom")
        return self._location


class _FakeRecordUseCase:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, vehicle_id: UUID, lat: float, lon: float, recorded_at: datetime, source: str) -> None:
        self.calls += 1


def _make_vehicle() -> Vehicle:
    return Vehicle(
        id=uuid4(),
        brand=Brand.TOYOTA,
        display_name="Test Toyota",
        vin="VIN123",
        license_plate="1234ABC",
        created_at=datetime.now(UTC),
        user_id=uuid4(),
    )


def _make_location(vehicle_id: UUID) -> VehicleLocation:
    now = datetime.now(UTC)
    return VehicleLocation(
        id=uuid4(),
        vehicle_id=vehicle_id,
        latitude=40.4168,
        longitude=-3.7038,
        recorded_at=now,
        received_at=now,
        source="pull",
    )


def test_successful_poll_produces_a_span(otel_span_exporter: InMemorySpanExporter) -> None:
    vehicle = _make_vehicle()
    location_provider = _FakeLocationProvider(location=_make_location(vehicle.id))
    record_use_case = _FakeRecordUseCase()
    scheduler = VehicleLocationScheduler(
        vehicle_repo=_FakeVehicleRepo([vehicle]),  # type: ignore[arg-type]
        config_repo=_FakeConfigRepo(),  # type: ignore[arg-type]
        location_provider=location_provider,  # type: ignore[arg-type]
        record_use_case=record_use_case,  # type: ignore[arg-type]
        interval_minutes=5,
    )

    scheduler._run()

    assert record_use_case.calls == 1
    spans = otel_span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "scheduler.vehicle_location.poll"
    assert spans[0].status.status_code == StatusCode.UNSET


def test_failed_poll_marks_span_as_error_without_raising(
    otel_span_exporter: InMemorySpanExporter,
) -> None:
    vehicle_ok = _make_vehicle()
    vehicle_fails = _make_vehicle()
    location_provider = _FakeLocationProvider(raises=True)
    record_use_case = _FakeRecordUseCase()
    scheduler = VehicleLocationScheduler(
        vehicle_repo=_FakeVehicleRepo([vehicle_fails, vehicle_ok]),  # type: ignore[arg-type]
        config_repo=_FakeConfigRepo(),  # type: ignore[arg-type]
        location_provider=location_provider,  # type: ignore[arg-type]
        record_use_case=record_use_case,  # type: ignore[arg-type]
        interval_minutes=5,
    )

    scheduler._run()  # must not raise — remaining vehicles still get polled

    assert len(location_provider.calls) == 2  # both vehicles attempted despite the first failing
    spans = otel_span_exporter.get_finished_spans()
    assert len(spans) == 2
    assert all(span.name == "scheduler.vehicle_location.poll" for span in spans)
    assert all(span.status.status_code == StatusCode.ERROR for span in spans)
    assert all(any(event.name == "exception" for event in span.events) for span in spans)
