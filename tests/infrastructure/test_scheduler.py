"""
Unit tests for ParkingIngestionScheduler's OpenTelemetry instrumentation.

Each per-city ingestion run must produce a root span
(`scheduler.parking_ingestion.run`), and a run whose use case raises must
mark that span as an error (with the exception recorded) WITHOUT the
scheduler's existing swallow-and-continue behavior changing — i.e. the
exception must never propagate out of start()/stop().
"""

from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from mobility_manager.infrastructure.scheduler import ParkingIngestionScheduler


class _FakeIngestUseCase:
    def __init__(self, *, raises: bool = False) -> None:
        self._raises = raises
        self.executed = False

    def execute(self) -> str:
        self.executed = True
        if self._raises:
            raise RuntimeError("ingestion boom")
        return "3 zones ingested"


def test_ingestion_run_produces_a_span(otel_span_exporter: InMemorySpanExporter) -> None:
    use_case = _FakeIngestUseCase()
    scheduler = ParkingIngestionScheduler(city_use_cases=[("madrid", use_case)], interval_hours=24)

    try:
        scheduler.start()  # triggers one immediate, synchronous run per city
    finally:
        scheduler.stop()

    assert use_case.executed
    spans = otel_span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "scheduler.parking_ingestion.run"
    assert spans[0].attributes is not None
    assert spans[0].attributes["mobility_manager.city"] == "madrid"
    assert spans[0].status.status_code == StatusCode.UNSET


def test_ingestion_run_failure_marks_span_as_error_without_raising(
    otel_span_exporter: InMemorySpanExporter,
) -> None:
    use_case = _FakeIngestUseCase(raises=True)
    scheduler = ParkingIngestionScheduler(city_use_cases=[("madrid", use_case)], interval_hours=24)

    try:
        scheduler.start()  # must not raise even though the use case does
    finally:
        scheduler.stop()

    assert use_case.executed
    spans = otel_span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].status.status_code == StatusCode.ERROR
    assert any(event.name == "exception" for event in spans[0].events)
