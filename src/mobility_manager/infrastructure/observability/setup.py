"""
Infrastructure: OpenTelemetry SDK setup.

Registers real TracerProvider/MeterProvider and the FastAPI/httpx/SQLAlchemy
auto-instrumentors — but ONLY when this module's init_observability() is
actually called. The single activation check is
config.get_otel_endpoint() (OTEL_EXPORTER_OTLP_ENDPOINT) — see app.py's
lifespan(), which is the only caller.

When init_observability() is never called, every OTel API call anywhere
else in the app (trace.get_tracer(...).start_as_current_span(...),
metrics.get_meter(...).create_counter(...).add(...)) transparently falls
back to OTel's built-in no-op implementation — this is how the OTel API is
specified to behave before any real provider is registered. That's why no
`if observability_enabled:` checks are scattered through scheduler/event
handler/metrics code (see design.md decision 3): those call sites are
always safe to call unconditionally.

The OTLP span/metric exporters read OTEL_EXPORTER_OTLP_ENDPOINT and
OTEL_EXPORTER_OTLP_HEADERS from the environment themselves (standard OTel
exporter behavior), so they're constructed with no explicit arguments here.
Only traces and metrics are wired up — no OTel logging handler/exporter is
ever configured (see design.md non-goals: no log export via OTLP).
"""

import logging
import os
import re
import threading
from typing import Any

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
    OTLPMetricExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace import Span
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_DEFAULT_TRACES_SAMPLER_RATIO = 0.25

# Both providers' shutdown() calls default to a 30s blocking join on their
# exporter's background worker thread if the OTLP backend is unreachable
# (see shutdown_observability() below) — bound each to 5s so worst-case
# lifespan teardown blocking stays around 10s total instead of ~60s.
_SHUTDOWN_TIMEOUT_MILLIS = 5000

# POST /vehicles/{token}/location (vehicles.py's push_vehicle_location) uses
# the {token} path segment as its *sole* authorization mechanism — no auth
# header. FastAPI/ASGI auto-instrumentation otherwise captures the raw
# request path (with the live token) into span attributes, so it must be
# redacted via a server_request_hook before export (see design.md risk on
# auto-instrumentation capturing sensitive data, and R1-001).
#
# GET /vehicles/{vehicle_id}/location shares the exact same path *shape*
# (/vehicles/<segment>/location) but isn't a secret (it's a UUID, guarded by
# a normal auth dependency) — so the method is checked too, to avoid also
# redacting that unrelated route's path.
_VEHICLE_LOCATION_PUSH_PATH_RE = re.compile(r"^/vehicles/(?P<token>[^/]+)/location$")
_REDACTED_TOKEN_SEGMENT = "REDACTED"

# Span attribute keys that can carry the raw request path/URL, across both
# the old and new (opt-in) OTel HTTP semantic conventions — see
# opentelemetry.instrumentation._semconv._set_http_target/_set_http_url.
_PATH_CARRYING_ATTRIBUTES = ("http.target", "http.url", "url.path", "url.full")


def _redact_vehicle_location_token(span: Span, scope: dict[str, Any]) -> None:
    """
    server_request_hook for FastAPIInstrumentor: strips the live device
    auth token out of span attributes for the vehicle-location-push route.

    http.route (the FastAPI route *template*, e.g.
    "/vehicles/{token}/location") never contains the actual token value and
    is left untouched; only the raw-path-derived attributes are redacted.
    """
    if not span.is_recording() or not isinstance(span, ReadableSpan):
        return

    if scope.get("method") != "POST":
        return

    path = scope.get("path")
    if not isinstance(path, str):
        return

    match = _VEHICLE_LOCATION_PUSH_PATH_RE.match(path)
    if match is None:
        return

    raw_token = match.group("token")
    attributes = span.attributes or {}
    for key in _PATH_CARRYING_ATTRIBUTES:
        value = attributes.get(key)
        if isinstance(value, str) and raw_token in value:
            span.set_attribute(key, value.replace(raw_token, _REDACTED_TOKEN_SEGMENT))


def _sampler_ratio() -> float:
    """
    Read the trace sampling ratio from OTEL_TRACES_SAMPLER_ARG, defaulting
    to 25% when unset or invalid (see design.md decision 8).
    """
    raw = os.environ.get("OTEL_TRACES_SAMPLER_ARG")
    if not raw:
        return _DEFAULT_TRACES_SAMPLER_RATIO
    try:
        return float(raw)
    except ValueError:
        logger.warning(
            "Invalid OTEL_TRACES_SAMPLER_ARG=%r — falling back to default ratio %s",
            raw,
            _DEFAULT_TRACES_SAMPLER_RATIO,
        )
        return _DEFAULT_TRACES_SAMPLER_RATIO


def init_observability(app: FastAPI, engine: Engine) -> tuple[TracerProvider, MeterProvider]:
    """
    Register real trace/metric providers and enable auto-instrumentation.

    Must only be called when config.get_otel_endpoint() returns a value —
    callers are responsible for guarding the call site (see app.py's
    lifespan()). Builds a Resource with service.name/service.version/
    deployment.environment, a ParentBased(TraceIdRatioBased(...)) sampler,
    and instruments the given FastAPI app instance, httpx globally, and the
    given SQLAlchemy engine (statement text only — bound parameter values
    are never captured, matching each instrumentor's default attribute set).

    Returns the (TracerProvider, MeterProvider) pair so the caller can flush
    them on shutdown via shutdown_observability().
    """
    resource = Resource.create(
        {
            SERVICE_NAME: "mobility-manager",
            SERVICE_VERSION: app.version,
            "deployment.environment": os.environ.get("DEPLOYMENT_ENVIRONMENT", "development"),
        }
    )

    sampler = ParentBased(TraceIdRatioBased(_sampler_ratio()))
    tracer_provider = TracerProvider(resource=resource, sampler=sampler)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter())
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # Auto-instrumentation: inbound HTTP (FastAPI), outbound HTTP (httpx —
    # Madrid SER, ElParking, Google OAuth, Toyota via pytoyoda), and Postgres
    # queries (SQLAlchemy). No "capture request/response body" or "capture
    # headers" options are enabled anywhere here — see design.md risk on
    # auto-instrumentation capturing sensitive data.
    FastAPIInstrumentor.instrument_app(app, server_request_hook=_redact_vehicle_location_token)
    HTTPXClientInstrumentor().instrument()
    SQLAlchemyInstrumentor().instrument(engine=engine)

    logger.info("OpenTelemetry observability initialized (trace sampler ratio=%s)", _sampler_ratio())

    return tracer_provider, meter_provider


def shutdown_observability(
    tracer_provider: TracerProvider | None,
    meter_provider: MeterProvider | None,
) -> None:
    """
    Flush and shut down both providers, guarded against being called when
    observability was never activated (both args None).

    Each shutdown is bounded to _SHUTDOWN_TIMEOUT_MILLIS (~5s) so an
    unreachable OTLP backend at process teardown adds at most ~10s of
    blocking to app shutdown, instead of the SDK's ~60s combined default
    (each provider's BatchSpanProcessor/PeriodicExportingMetricReader
    defaults to a 30s blocking join on its exporter's background worker
    thread — see R4-001). MeterProvider.shutdown() accepts timeout_millis
    directly. TracerProvider.shutdown() does not accept a timeout argument
    on the installed SDK version (BatchSpanProcessor.shutdown() hardcodes
    the SDK's 30s default internally with no way to override it through the
    public provider/processor API), so it's run on a daemon thread and
    joined with a timeout instead; if the backend is still unreachable
    after the timeout, that thread is abandoned (harmless — daemon threads
    don't block process exit) and teardown continues.
    """
    if tracer_provider is not None:
        shutdown_thread = threading.Thread(target=tracer_provider.shutdown, daemon=True)
        shutdown_thread.start()
        shutdown_thread.join(timeout=_SHUTDOWN_TIMEOUT_MILLIS / 1000)
    if meter_provider is not None:
        meter_provider.shutdown(timeout_millis=_SHUTDOWN_TIMEOUT_MILLIS)
