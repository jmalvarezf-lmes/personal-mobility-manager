"""
Unit tests for infrastructure/observability/metrics.py.

Uses the shared in-memory MeterProvider registered once in tests/conftest.py
(the OTel API only allows a global MeterProvider to be set once per
process) to assert each `record_*` function increments the right counter
with the right (and only the right) labels, and that each function's
signature is bounded/typed enough to guard against future PII leakage via
metric labels (see design.md decision 7).
"""

import inspect
from typing import Any

from opentelemetry.sdk.metrics.export import InMemoryMetricReader, MetricsData

from mobility_manager.infrastructure.observability.metrics import (
    record_ambient_label_lookup,
    record_ingestion_run,
    record_notification_dispatch,
    record_vehicle_poll,
)


def _find_point_value(metrics_data: MetricsData, metric_name: str, attributes: dict[str, Any]) -> int:
    for resource_metrics in metrics_data.resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                if metric.name != metric_name:
                    continue
                for point in metric.data.data_points:
                    if dict(point.attributes) == attributes:
                        return int(point.value)
    return 0


def _value_for(reader: InMemoryMetricReader, metric_name: str, attributes: dict[str, Any]) -> int:
    data = reader.get_metrics_data()
    if data is None:
        return 0
    return _find_point_value(data, metric_name, attributes)


def test_record_notification_dispatch_increments_counter_with_channel_and_success(
    otel_metric_reader: InMemoryMetricReader,
) -> None:
    attributes = {"channel": "telegram", "success": True}
    before = _value_for(otel_metric_reader, "mobility_manager.notification_dispatch", attributes)

    record_notification_dispatch(channel="telegram", success=True)

    after = _value_for(otel_metric_reader, "mobility_manager.notification_dispatch", attributes)
    assert after == before + 1


def test_record_notification_dispatch_labels_failure_separately(
    otel_metric_reader: InMemoryMetricReader,
) -> None:
    attributes = {"channel": "telegram", "success": False}
    before = _value_for(otel_metric_reader, "mobility_manager.notification_dispatch", attributes)

    record_notification_dispatch(channel="telegram", success=False)

    after = _value_for(otel_metric_reader, "mobility_manager.notification_dispatch", attributes)
    assert after == before + 1


def test_record_ingestion_run_increments_counter_with_city_and_success(
    otel_metric_reader: InMemoryMetricReader,
) -> None:
    attributes = {"city": "madrid", "success": True}
    before = _value_for(otel_metric_reader, "mobility_manager.ingestion_run", attributes)

    record_ingestion_run(city="madrid", success=True)

    after = _value_for(otel_metric_reader, "mobility_manager.ingestion_run", attributes)
    assert after == before + 1


def test_record_ingestion_run_labels_failure_separately(
    otel_metric_reader: InMemoryMetricReader,
) -> None:
    attributes = {"city": "madrid", "success": False}
    before = _value_for(otel_metric_reader, "mobility_manager.ingestion_run", attributes)

    record_ingestion_run(city="madrid", success=False)

    after = _value_for(otel_metric_reader, "mobility_manager.ingestion_run", attributes)
    assert after == before + 1


def test_record_vehicle_poll_increments_counter_with_success(
    otel_metric_reader: InMemoryMetricReader,
) -> None:
    attributes = {"success": True}
    before = _value_for(otel_metric_reader, "mobility_manager.vehicle_poll", attributes)

    record_vehicle_poll(success=True)

    after = _value_for(otel_metric_reader, "mobility_manager.vehicle_poll", attributes)
    assert after == before + 1


def test_record_vehicle_poll_labels_failure_separately(
    otel_metric_reader: InMemoryMetricReader,
) -> None:
    attributes = {"success": False}
    before = _value_for(otel_metric_reader, "mobility_manager.vehicle_poll", attributes)

    record_vehicle_poll(success=False)

    after = _value_for(otel_metric_reader, "mobility_manager.vehicle_poll", attributes)
    assert after == before + 1


def test_record_ambient_label_lookup_increments_counter_with_status(
    otel_metric_reader: InMemoryMetricReader,
) -> None:
    attributes = {"status": "found"}
    before = _value_for(otel_metric_reader, "mobility_manager.ambient_label_lookup", attributes)

    record_ambient_label_lookup(status="found")

    after = _value_for(otel_metric_reader, "mobility_manager.ambient_label_lookup", attributes)
    assert after == before + 1


def test_record_ambient_label_lookup_labels_not_found_and_error_separately(
    otel_metric_reader: InMemoryMetricReader,
) -> None:
    not_found_attrs = {"status": "not_found"}
    error_attrs = {"status": "error"}
    before_not_found = _value_for(otel_metric_reader, "mobility_manager.ambient_label_lookup", not_found_attrs)
    before_error = _value_for(otel_metric_reader, "mobility_manager.ambient_label_lookup", error_attrs)

    record_ambient_label_lookup(status="not_found")
    record_ambient_label_lookup(status="error")

    assert (
        _value_for(otel_metric_reader, "mobility_manager.ambient_label_lookup", not_found_attrs)
        == before_not_found + 1
    )
    assert _value_for(otel_metric_reader, "mobility_manager.ambient_label_lookup", error_attrs) == before_error + 1


def test_record_ambient_label_lookup_signature_is_bounded_and_typed() -> None:
    sig = inspect.signature(record_ambient_label_lookup)
    assert list(sig.parameters) == ["status"]
    assert all(p.kind != inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
    assert sig.parameters["status"].annotation is str


def test_record_notification_dispatch_signature_is_bounded_and_typed() -> None:
    """Guards against future PII leakage: only channel (str) and success (bool) — no **kwargs passthrough."""
    sig = inspect.signature(record_notification_dispatch)
    assert list(sig.parameters) == ["channel", "success"]
    assert all(p.kind != inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
    assert sig.parameters["channel"].annotation is str
    assert sig.parameters["success"].annotation is bool


def test_record_ingestion_run_signature_is_bounded_and_typed() -> None:
    sig = inspect.signature(record_ingestion_run)
    assert list(sig.parameters) == ["city", "success"]
    assert all(p.kind != inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
    assert sig.parameters["city"].annotation is str
    assert sig.parameters["success"].annotation is bool


def test_record_vehicle_poll_signature_is_bounded_and_typed() -> None:
    sig = inspect.signature(record_vehicle_poll)
    assert list(sig.parameters) == ["success"]
    assert all(p.kind != inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
    assert sig.parameters["success"].annotation is bool
