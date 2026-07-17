"""
Unit tests for infrastructure/observability/setup.py.

Covers:
  - _sampler_ratio()'s three branches (unset env var, valid override,
    invalid override falling back with a warning) — see R3-001.
  - The FastAPIInstrumentor server_request_hook that redacts the live
    device auth token from spans on the vehicle-location-push route — see
    R1-001 and design.md's risk on auto-instrumentation capturing sensitive
    data. POST /vehicles/{token}/location (vehicles.py's
    push_vehicle_location) uses the {token} path segment as its *sole*
    authorization mechanism (no auth header), so the raw path must never
    reach span attributes that get exported to the configured OTLP backend.
  - shutdown_observability()'s bounded-timeout behavior when a provider's
    exporter is slow/unreachable — see R4-001.
"""

import logging
import time
from collections.abc import Sequence
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import SpanKind
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from mobility_manager.infrastructure.observability import setup as observability_setup
from mobility_manager.infrastructure.observability.setup import (
    _DEFAULT_TRACES_SAMPLER_RATIO,
    _redact_vehicle_location_token,
    _sampler_ratio,
    shutdown_observability,
)
from mobility_manager.presentation.api.limiter import limiter
from mobility_manager.presentation.api.routers.vehicles import router as vehicles_router


def test_sampler_ratio_defaults_when_env_var_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OTEL_TRACES_SAMPLER_ARG", raising=False)

    assert _sampler_ratio() == _DEFAULT_TRACES_SAMPLER_RATIO


def test_sampler_ratio_uses_valid_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTEL_TRACES_SAMPLER_ARG", "0.5")

    assert _sampler_ratio() == 0.5


def test_sampler_ratio_falls_back_and_warns_on_invalid_override(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("OTEL_TRACES_SAMPLER_ARG", "not-a-float")

    with caplog.at_level(logging.WARNING):
        ratio = _sampler_ratio()

    assert ratio == _DEFAULT_TRACES_SAMPLER_RATIO
    assert any("Invalid OTEL_TRACES_SAMPLER_ARG" in record.message for record in caplog.records)


def _build_instrumented_app() -> FastAPI:
    """Minimal FastAPI app carrying just the real vehicles router, wired up
    with the same rate-limiter plumbing app.py uses (push_vehicle_location
    is rate-limited), then instrumented exactly as init_observability()
    instruments the real app."""
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)
    app.include_router(vehicles_router)
    FastAPIInstrumentor.instrument_app(app, server_request_hook=_redact_vehicle_location_token)
    return app


def test_vehicle_location_push_span_redacts_token(otel_span_exporter: InMemorySpanExporter) -> None:
    app = _build_instrumented_app()
    fake_token = "super-secret-device-token-12345"

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            client.post(
                f"/vehicles/{fake_token}/location",
                json={"lat": 40.4, "lon": -3.7, "recorded_at": "2026-01-01T00:00:00Z"},
            )
    finally:
        FastAPIInstrumentor.uninstrument_app(app)

    spans = otel_span_exporter.get_finished_spans()
    assert spans, "expected at least one span to be captured for the push request"

    for span in spans:
        assert fake_token not in span.name
        for value in (span.attributes or {}).values():
            assert fake_token not in str(value)

    assert any(
        any("REDACTED" in str(value) for value in (span.attributes or {}).values()) for span in spans
    ), "expected the redacted path to show up in at least one span attribute"


def test_other_route_spans_are_unaffected_by_the_redaction_hook(
    otel_span_exporter: InMemorySpanExporter,
) -> None:
    """http.route (the route template) never carries the raw token, and
    other routes' spans must not be touched by the hook at all."""
    app = _build_instrumented_app()

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            client.get("/vehicles/00000000-0000-0000-0000-000000000000/location")
    finally:
        FastAPIInstrumentor.uninstrument_app(app)

    spans = otel_span_exporter.get_finished_spans()
    assert spans, "expected at least one span to be captured for the GET request"
    for span in spans:
        assert not any("REDACTED" in str(value) for value in (span.attributes or {}).values())

    server_spans = [span for span in spans if span.kind == SpanKind.SERVER]
    assert server_spans, "expected the main ASGI server span to be captured"
    assert (server_spans[0].attributes or {}).get("http.route") == "/vehicles/{vehicle_id}/location"


class _SlowSpanExporter(SpanExporter):
    """Simulates an unreachable/slow OTLP backend: shutdown() blocks for
    longer than the configured shutdown timeout bound."""

    def __init__(self, delay_seconds: float) -> None:
        self._delay_seconds = delay_seconds

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        return SpanExportResult.SUCCESS

    def shutdown(self, timeout_millis: int = 30000) -> None:
        time.sleep(self._delay_seconds)


def test_shutdown_observability_bounds_tracer_provider_blocking_on_slow_exporter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TracerProvider.shutdown() has no timeout parameter on the installed
    SDK version, so shutdown_observability() bounds it by running it on a
    joined-with-timeout daemon thread instead (see R4-001). This shrinks
    the bound to 200ms so the test itself stays fast, and uses a fake
    exporter that sleeps far longer than that to prove the call returns
    without waiting for the slow exporter."""
    monkeypatch.setattr(observability_setup, "_SHUTDOWN_TIMEOUT_MILLIS", 200)
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(BatchSpanProcessor(_SlowSpanExporter(delay_seconds=2.0)))

    start = time.monotonic()
    shutdown_observability(tracer_provider, None)
    elapsed = time.monotonic() - start

    assert elapsed < 1.0, f"shutdown_observability() blocked for {elapsed:.2f}s despite a 200ms bound"


def test_shutdown_observability_passes_timeout_millis_to_meter_provider() -> None:
    meter_provider = MagicMock()

    shutdown_observability(None, meter_provider)

    meter_provider.shutdown.assert_called_once_with(
        timeout_millis=observability_setup._SHUTDOWN_TIMEOUT_MILLIS
    )


def test_shutdown_observability_is_a_no_op_when_both_providers_are_none() -> None:
    shutdown_observability(None, None)
