## 1. Dependencies & configuration

- [x] 1.1 Add `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-httpx`, and `opentelemetry-instrumentation-sqlalchemy` to `pyproject.toml`.
- [x] 1.2 Add a `config.py` accessor (e.g. `get_otel_endpoint()`) that reads `OTEL_EXPORTER_OTLP_ENDPOINT` and returns `None` when unset, used as the single activation check.
- [x] 1.3 Document `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_TRACES_SAMPLER`, and `OTEL_TRACES_SAMPLER_ARG` in `.env.example`, with a comment noting these are standard OTel variables (copy-pasteable from Grafana Cloud's OTLP onboarding page) and that observability is fully inactive when the endpoint is unset.

## 2. Observability module — SDK setup

- [x] 2.1 Create `src/mobility_manager/infrastructure/observability/__init__.py`.
- [x] 2.2 Create `src/mobility_manager/infrastructure/observability/setup.py` with an `init_observability(app, engine) -> tuple[TracerProvider, MeterProvider]` function that: builds a `Resource` with `service.name`, `service.version`, `deployment.environment`; constructs a `TracerProvider` with a `ParentBased(TraceIdRatioBased(...))` sampler defaulting to 25% (overridable via `OTEL_TRACES_SAMPLER_ARG`); constructs a `MeterProvider` with a `PeriodicExportingMetricReader`; wires OTLP/HTTP span and metric exporters using `OTEL_EXPORTER_OTLP_ENDPOINT`/`OTEL_EXPORTER_OTLP_HEADERS`; and calls `FastAPIInstrumentor.instrument_app(app)`, `HTTPXClientInstrumentor().instrument()`, and `SQLAlchemyInstrumentor().instrument(engine=engine)`.
- [x] 2.3 Ensure `init_observability` is only invoked when `get_otel_endpoint()` returns a value; when it's not called, confirm (by inspection/test) that `trace.get_tracer(...)` and `metrics.get_meter(...)` fall back to OTel's default no-op implementations.
- [x] 2.4 Add a `shutdown_observability(tracer_provider, meter_provider)` helper that flushes/shuts down both providers, guarded against being called when they were never created.

## 3. Observability module — custom metrics

- [x] 3.1 Create `src/mobility_manager/infrastructure/observability/metrics.py` that gets a module-level `Meter` via `metrics.get_meter("mobility_manager")` and pre-registers three counters: notification dispatch, ingestion run, vehicle poll.
- [x] 3.2 Add `record_notification_dispatch(channel: str, success: bool) -> None`.
- [x] 3.3 Add `record_ingestion_run(city: str, success: bool) -> None`.
- [x] 3.4 Add `record_vehicle_poll(success: bool) -> None`.
- [x] 3.5 Add a short module docstring/comment documenting the extension pattern: new metric = one instrument registration + one typed recording function, no other wiring needed.

## 4. Wire into app lifespan

- [x] 4.1 In `presentation/api/app.py`'s `lifespan()`, after the engine is constructed, call `init_observability(app, engine)` when `get_otel_endpoint()` is configured; store the returned providers for teardown.
- [x] 4.2 In the teardown half of `lifespan()`, call `shutdown_observability(...)` alongside the existing scheduler `.stop()` calls.
- [x] 4.3 Verify app startup and `/health` still work identically with no `OTEL_EXPORTER_OTLP_ENDPOINT` set (no new required env vars, no crash, no behavior change).

## 5. Manual tracing & metrics — schedulers

- [x] 5.1 In `infrastructure/scheduler.py` (`ParkingIngestionScheduler`), wrap each per-city ingestion job run in a root span (`tracer.start_as_current_span("scheduler.parking_ingestion.run")`), recording the exception and error status on failure without changing the existing swallow-and-continue behavior, and call `record_ingestion_run(city=..., success=...)` at the end of each run.
- [x] 5.2 In `infrastructure/vehicle_location_scheduler.py` (`VehicleLocationScheduler`), wrap each poll in a root span (`tracer.start_as_current_span("scheduler.vehicle_location.poll")`) with the same exception-recording pattern, and call `record_vehicle_poll(success=...)` at the end of each poll.

## 6. Manual tracing & metrics — event handlers

- [x] 6.1 In `application/event_handlers/notification_dispatch_handler.py`, wrap `handle()` in a root span (`tracer.start_as_current_span("event_handler.notification_dispatch")`) with exception recording, and call `record_notification_dispatch(channel=..., success=...)` once per channel dispatch attempt.
- [x] 6.2 In `application/event_handlers/ser_ticket_trigger_handler.py`, wrap `handle()` in a root span (`tracer.start_as_current_span("event_handler.ser_ticket_trigger")`) with the same exception-recording pattern (no dedicated custom metric for this handler in v1).

## 7. Tests

- [x] 7.1 Add unit tests for `infrastructure/observability/metrics.py` using an `InMemoryMetricReader` (or equivalent OTel test utility) asserting each `record_*` function increments the right counter with the right (and only the right) labels.
- [x] 7.2 Add a test asserting the app starts successfully and `/health` responds normally with no `OTEL_EXPORTER_OTLP_ENDPOINT` set.
- [x] 7.3 Add tests (using `InMemorySpanExporter`) verifying scheduler job runs and event handler dispatches each produce a span, and that a span is marked as an error (with the exception recorded) when the underlying job/handler raises internally, without the job/handler's existing swallow-and-continue behavior changing.
- [x] 7.4 Add a test confirming the metrics module's `record_*` function signatures only accept the documented bounded parameters (channel/city/success), not arbitrary free-text values, to guard against future PII leakage via labels.
- [x] 7.5 Run the full test suite and confirm no existing tests (including hand-rolled fakes in `tests/application/`) are affected by the new instrumentation.

## 8. Manual verification (deferred if no live stack available)

- [ ] 8.1 With `OTEL_EXPORTER_OTLP_ENDPOINT`/`OTEL_EXPORTER_OTLP_HEADERS` pointed at a real Grafana Cloud account, run the app locally, exercise an API route, an outbound call, a DB query, a scheduler tick, and an event dispatch, and confirm corresponding traces and metrics appear in Grafana Cloud (Tempo/Mimir).
- [ ] 8.2 Confirm the 25% sampling rate is visibly in effect (not every request produces a trace) and that overriding `OTEL_TRACES_SAMPLER_ARG` changes the observed rate.
