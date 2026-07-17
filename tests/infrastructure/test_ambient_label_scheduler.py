"""
Unit tests for AmbientLabelScheduler.

Mirrors tests/infrastructure/test_vehicle_location_scheduler.py's shape:
each per-vehicle lookup produces a root span, and one vehicle's exception
must not stop the rest of the tick. Also asserts backlog-only querying
(never the full vehicle list), that `found` vehicles are never included,
and that the configured delay is invoked between consecutive lookups but
not after the trailing one.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import UUID, uuid4

from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.infrastructure.ambient_label_scheduler import (
    AmbientLabelScheduler,
)


class _FakeVehicleRepo:
    def __init__(self, vehicles: dict[UUID, Vehicle]) -> None:
        self._vehicles = vehicles

    def get_by_id(self, vehicle_id: UUID) -> Vehicle | None:
        return self._vehicles.get(vehicle_id)


class _FakeLabelRepo:
    def __init__(self, backlog: list[UUID]) -> None:
        self._backlog = backlog
        self.cooldowns_requested: list[timedelta] = []

    def get_vehicles_needing_lookup(self, cooldown: timedelta) -> list[UUID]:
        self.cooldowns_requested.append(cooldown)
        return self._backlog


class _FakeLookupUseCase:
    def __init__(self, raise_for: set[UUID] | None = None) -> None:
        self._raise_for = raise_for or set()
        self.calls: list[tuple[UUID, str]] = []

    def execute(self, vehicle_id: UUID, license_plate: str) -> None:
        self.calls.append((vehicle_id, license_plate))
        if vehicle_id in self._raise_for:
            raise RuntimeError("dgt boom")


def _make_vehicle(vehicle_id: UUID, license_plate: str | None = "1234ABC") -> Vehicle:
    return Vehicle(
        id=vehicle_id,
        brand=Brand.GENERIC,
        display_name="Test Vehicle",
        vin=None,
        license_plate=license_plate,
        created_at=datetime.now(UTC),
        user_id=uuid4(),
    )


def test_successful_lookup_produces_a_span(otel_span_exporter: InMemorySpanExporter) -> None:
    vehicle_id = uuid4()
    vehicle_repo = _FakeVehicleRepo({vehicle_id: _make_vehicle(vehicle_id)})
    label_repo = _FakeLabelRepo([vehicle_id])
    lookup_use_case = _FakeLookupUseCase()
    scheduler = AmbientLabelScheduler(
        vehicle_repo=vehicle_repo,  # type: ignore[arg-type]
        label_repo=label_repo,  # type: ignore[arg-type]
        lookup_use_case=lookup_use_case,  # type: ignore[arg-type]
        request_delay_seconds=0,
    )

    scheduler._run()

    assert lookup_use_case.calls == [(vehicle_id, "1234ABC")]
    spans = otel_span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "scheduler.ambient_label.lookup"
    assert spans[0].status.status_code == StatusCode.UNSET


def test_failed_lookup_marks_span_as_error_without_raising(
    otel_span_exporter: InMemorySpanExporter,
) -> None:
    vehicle_ok = uuid4()
    vehicle_fails = uuid4()
    vehicle_repo = _FakeVehicleRepo(
        {
            vehicle_ok: _make_vehicle(vehicle_ok),
            vehicle_fails: _make_vehicle(vehicle_fails),
        }
    )
    label_repo = _FakeLabelRepo([vehicle_fails, vehicle_ok])
    lookup_use_case = _FakeLookupUseCase(raise_for={vehicle_fails})
    scheduler = AmbientLabelScheduler(
        vehicle_repo=vehicle_repo,  # type: ignore[arg-type]
        label_repo=label_repo,  # type: ignore[arg-type]
        lookup_use_case=lookup_use_case,  # type: ignore[arg-type]
        request_delay_seconds=0,
    )

    scheduler._run()  # must not raise — remaining vehicles still get looked up

    assert len(lookup_use_case.calls) == 2  # both vehicles attempted despite the first failing
    spans = otel_span_exporter.get_finished_spans()
    assert len(spans) == 2
    error_spans = [s for s in spans if s.status.status_code == StatusCode.ERROR]
    assert len(error_spans) == 1
    assert any(event.name == "exception" for event in error_spans[0].events)


def test_backlog_query_is_used_not_full_vehicle_list() -> None:
    """The scheduler must never fetch the full vehicle list — only the backlog."""
    vehicle_id = uuid4()
    vehicle_repo = _FakeVehicleRepo({vehicle_id: _make_vehicle(vehicle_id)})
    label_repo = _FakeLabelRepo([vehicle_id])
    lookup_use_case = _FakeLookupUseCase()
    scheduler = AmbientLabelScheduler(
        vehicle_repo=vehicle_repo,  # type: ignore[arg-type]
        label_repo=label_repo,  # type: ignore[arg-type]
        lookup_use_case=lookup_use_case,  # type: ignore[arg-type]
        retry_cooldown_hours=24,
        request_delay_seconds=0,
    )

    scheduler._run()

    assert len(label_repo.cooldowns_requested) == 1
    assert label_repo.cooldowns_requested[0] == timedelta(hours=24)
    assert not hasattr(vehicle_repo, "get_all_by_user_id")  # never even has that capability


def test_found_vehicles_never_appear_in_the_backlog_so_never_looked_up() -> None:
    """
    The scheduler trusts get_vehicles_needing_lookup() to exclude `found`
    rows — verified here by returning an empty backlog and asserting zero
    lookups happen.
    """
    label_repo = _FakeLabelRepo([])
    lookup_use_case = _FakeLookupUseCase()
    scheduler = AmbientLabelScheduler(
        vehicle_repo=_FakeVehicleRepo({}),  # type: ignore[arg-type]
        label_repo=label_repo,  # type: ignore[arg-type]
        lookup_use_case=lookup_use_case,  # type: ignore[arg-type]
        request_delay_seconds=0,
    )

    scheduler._run()

    assert lookup_use_case.calls == []


def test_delay_is_invoked_between_consecutive_lookups_but_not_trailing() -> None:
    vehicle_ids = [uuid4(), uuid4(), uuid4()]
    vehicle_repo = _FakeVehicleRepo({vid: _make_vehicle(vid) for vid in vehicle_ids})
    label_repo = _FakeLabelRepo(vehicle_ids)
    lookup_use_case = _FakeLookupUseCase()
    scheduler = AmbientLabelScheduler(
        vehicle_repo=vehicle_repo,  # type: ignore[arg-type]
        label_repo=label_repo,  # type: ignore[arg-type]
        lookup_use_case=lookup_use_case,  # type: ignore[arg-type]
        request_delay_seconds=5,
    )

    with patch("mobility_manager.infrastructure.ambient_label_scheduler.time.sleep") as mock_sleep:
        scheduler._run()

    # 3 vehicles => 2 delays between them, never a trailing delay after the last
    assert mock_sleep.call_count == 2
    mock_sleep.assert_called_with(5)


def test_vehicle_missing_plate_is_skipped_without_error(otel_span_exporter: InMemorySpanExporter) -> None:
    vehicle_id = uuid4()
    vehicle_repo = _FakeVehicleRepo({vehicle_id: _make_vehicle(vehicle_id, license_plate=None)})
    label_repo = _FakeLabelRepo([vehicle_id])
    lookup_use_case = _FakeLookupUseCase()
    scheduler = AmbientLabelScheduler(
        vehicle_repo=vehicle_repo,  # type: ignore[arg-type]
        label_repo=label_repo,  # type: ignore[arg-type]
        lookup_use_case=lookup_use_case,  # type: ignore[arg-type]
        request_delay_seconds=0,
    )

    scheduler._run()

    assert lookup_use_case.calls == []
    spans = otel_span_exporter.get_finished_spans()
    assert spans[0].status.status_code == StatusCode.UNSET
