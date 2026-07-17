## Why

The backend currently has no visibility beyond stdlib log lines: HTTP requests, outbound calls to Madrid SER/ElParking/Google/Toyota, database queries, scheduled ingestion/polling jobs, and event-driven notification dispatch all run with zero metrics or traces. Failures in background jobs and event handlers are silently swallowed (`logger.exception` + continue), so there is currently no way to see error rates or latency trends without grepping logs after the fact. As the project is expected to see more usage, adding OpenTelemetry now — before scale makes retrofitting harder — gives us request/DB/outbound-call tracing and health metrics for the background jobs.

## What Changes

- Add the OpenTelemetry SDK plus auto-instrumentation for FastAPI (inbound HTTP), httpx (outbound calls to Madrid SER, ElParking, Google OAuth, Toyota), and SQLAlchemy (Postgres queries).
- Add manual root spans around each APScheduler job run (`ParkingIngestionScheduler`, `VehicleLocationScheduler`) and each event handler dispatch (`NotificationDispatchHandler`, `SerTicketTriggerHandler`), since these execute outside any request context and would otherwise have no trace coverage.
- Add a small `observability` module exposing pre-registered custom metric instruments and typed recording functions, so adding a new metric later is a one-function addition rather than new OTel plumbing. Initial metrics: notification dispatch success/failure by channel, ingestion success/failure by city, vehicle poll success/failure.
- Configure the OTLP exporter to send traces and metrics only (no logs pipeline, to avoid any risk of PII leaking through log export) to Grafana Cloud's OTLP endpoint, authenticated via Basic Auth (instance ID + API token).
- Wire OTel SDK initialization/shutdown into the existing FastAPI `lifespan` context manager in `app.py`, alongside the existing scheduler/repo wiring.
- Activation is implicit: observability is fully active when an OTLP endpoint env var is configured, and a no-op/disabled instrumentation path when it is not — no separate enable/disable flag. This keeps the app runnable with zero telemetry for anyone without Grafana Cloud credentials configured.
- Add a trace sampling rate env var, defaulting to 25%.
- Add resource attributes (`service.name`, `service.version`, `deployment.environment`) so signals are identifiable in Grafana Cloud.

## Capabilities

### New Capabilities
- `observability`: Backend-wide OpenTelemetry instrumentation (traces + metrics) covering HTTP requests, outbound HTTP calls, database queries, scheduled jobs, and event handler dispatch, exported via OTLP to a configurable endpoint (Grafana Cloud), with sampling and activation controlled by environment variables, and an extensible custom-metrics module.

### Modified Capabilities
(none — no existing capability's requirements change; this is additive cross-cutting instrumentation)

## Impact

- **Affected code**: `src/mobility_manager/presentation/api/app.py` (lifespan wiring), new `src/mobility_manager/infrastructure/observability/` module (SDK init, metrics registry), `infrastructure/scheduler.py`, `infrastructure/vehicle_location_scheduler.py`, `application/event_handlers/notification_dispatch_handler.py`, `application/event_handlers/ser_ticket_trigger_handler.py`, `config.py` (new env var accessors), `pyproject.toml` (new dependencies), `.env.example` (new OTel-related vars documented).
- **New dependencies**: `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-httpx`, `opentelemetry-instrumentation-sqlalchemy`.
- **No infrastructure changes**: no new containers in `docker-compose.yml` — export goes directly to Grafana Cloud over OTLP/HTTP, no local Collector.
- **No frontend changes**: this change is backend-only.
- **Runtime behavior**: request latency overhead from instrumentation is expected to be negligible; the background export path (`BatchSpanProcessor` / periodic metric reader) runs off the request thread and must never block or fail a request/job even if Grafana Cloud is unreachable.
