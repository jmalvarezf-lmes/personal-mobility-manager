## Context

The backend is a single-process FastAPI app (`presentation/api/app.py`) run via `uvicorn`, with all wiring (repos, schedulers, event handlers) done manually inside a `lifespan()` context manager — there is no DI framework. Three kinds of work happen outside a normal request/response cycle and therefore have no natural place to attach telemetry today:

- **APScheduler jobs** (`ParkingIngestionScheduler`, `VehicleLocationScheduler`) run in APScheduler's own thread pool, not the asyncio event loop, and not inside any HTTP request.
- **Event handlers** (`NotificationDispatchHandler`, `SerTicketTriggerHandler`) run synchronously inside `InMemoryEventPublisher.publish()`, in the caller's thread, with no queue or persistence. Both currently wrap their logic in try/except and `logger.exception(...)` — errors are swallowed and never surfaced beyond a log line.

Everything else (inbound HTTP via FastAPI routers, outbound HTTP via `httpx` — used uniformly for Madrid SER, ElParking, Google OAuth, and Toyota via `pytoyoda`, and Postgres access via a single `lru_cache`'d SQLAlchemy Core `Engine`) sits on well-defined library boundaries that OTel has off-the-shelf auto-instrumentation for.

There is currently zero observability tooling in the project (confirmed: no `opentelemetry`, `prometheus`, `sentry`, `datadog`, or `newrelic` in dependencies). Config today is plain `os.environ.get(...)` accessors in `config.py`, loaded via `load_dotenv()`.

## Goals / Non-Goals

**Goals:**
- Trace inbound requests, outbound calls, and DB queries automatically via OTel instrumentation libraries.
- Trace scheduler job runs and event handler dispatches manually, since they have no auto-instrumentation hook.
- Emit three initial custom business metrics (notification dispatch, ingestion run, vehicle poll — each success/failure) via a small, centralized, easily-extensible module.
- Export traces and metrics only, directly to Grafana Cloud via OTLP/HTTP, with no local Collector and no new containers.
- Make activation implicit (endpoint configured = on; unset = off) with zero-overhead, zero-crash behavior when off.
- Keep sampling and the OTLP endpoint/credentials configurable via environment variables, following the existing `config.py` pattern.

**Non-Goals:**
- No log export via OTLP (explicitly excluded to avoid any PII exposure path).
- No frontend/browser instrumentation (Grafana Faro or otherwise) — backend only, this round.
- No local OTel Collector, Jaeger, Prometheus, or Grafana container — export goes straight to Grafana Cloud.
- No tail-based or error-biased sampling — uniform head-based sampling only, v1.
- No dashboards-as-code / Grafana dashboard provisioning — dashboard construction in Grafana Cloud is manual, out of scope for this change.

## Decisions

**1. Direct OTLP export to Grafana Cloud, no local Collector.**
Grafana Cloud's OTLP gateway accepts OTLP/HTTP directly with Basic Auth (`instance ID : API token`), so the SDK's `OTLPSpanExporter`/OTLP metric exporter can point straight at it. Alternative considered: stand up an OTel Collector (+ Jaeger/Prometheus/Grafana) in `docker-compose.yml`. Rejected — adds three more containers to operate for a single-process personal project, when Grafana Cloud already hosts Tempo/Mimir and accepts direct ingestion. Revisit only if the app moves to multi-service and a Collector's batching/fan-out becomes valuable.

**2. Use standard OTel environment variables, not app-specific ones.**
`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_TRACES_SAMPLER`, `OTEL_TRACES_SAMPLER_ARG` are the exact variable names Grafana Cloud's own onboarding page tells users to set. Using them directly (rather than inventing `GRAFANA_CLOUD_*` equivalents and translating) means the user can copy-paste from Grafana Cloud's UI with no translation layer, and the OTel SDK/exporters pick many of them up automatically.

**3. Activation is implicit via `OTEL_EXPORTER_OTLP_ENDPOINT` presence — no separate flag.**
The OTel API is a safe no-op by default: `trace.get_tracer(...)` and `metrics.get_meter(...)` return no-op implementations until a real `TracerProvider`/`MeterProvider` is registered. So the SDK init step in `lifespan()` only registers real providers (and only calls `FastAPIInstrumentor`, `HTTPXClientInstrumentor`, `SQLAlchemyInstrumentor`) when the endpoint env var is set. Every call site that creates manual spans or records metrics (schedulers, event handlers, the metrics module) calls the OTel API unconditionally — no `if observability_enabled:` checks scattered through business code. When the endpoint is unset, those calls are inert.

**4. Manual root spans for schedulers and event handlers.**
Because APScheduler jobs run outside the asyncio loop and event handlers run outside any request, there's no ambient trace context to attach to automatically. Each scheduler job's `run()`/tick method and each event handler's `handle()` method starts its own root span (`tracer.start_as_current_span(...)`) at the top, and records the outcome (including calling `span.record_exception()` / setting an error status when the existing try/except catches something) — without changing the existing swallow-and-continue error-handling behavior itself.

**5. Centralized, extensible custom-metrics module.**
A new `infrastructure/observability/metrics.py` pre-creates all counters at module load time and exposes small typed functions (e.g. `record_notification_dispatch(channel: str, success: bool)`). Call sites never touch the raw OTel metrics API. Adding a 4th metric later is: add one `create_counter`/`create_histogram` call and one recording function — no changes to SDK init or instrumentation wiring. Alternative considered: let each call site create its own instrument ad hoc via `metrics.get_meter(__name__).create_counter(...)`. Rejected — invites inconsistent naming/label conventions across the codebase and makes it harder to see the full metric surface at a glance.

**6. SDK init/shutdown lives in `lifespan()`, next to existing wiring.**
`app.py`'s `lifespan()` already constructs the engine, repos, and schedulers in one place before `yield` and tears them down after. OTel SDK setup (resource attributes, `TracerProvider`, `MeterProvider`, exporters, calling the three auto-instrumentors against the already-constructed `app`/`engine`) follows the same pattern, and `tracer_provider.shutdown()` / `meter_provider.shutdown()` (to flush any buffered batch) happens in the teardown half, alongside existing scheduler `.stop()` calls.

**7. Metric labels and span attributes are restricted to bounded, non-PII values.**
Labels are things like `channel` (`telegram`/`email`/etc.), `city`, and `success` (boolean) — small closed sets, never a user ID, plate number, email, or free-text value. This is enforced by the recording functions' signatures in the metrics module (typed parameters, not a generic `**attributes` passthrough), not by convention alone.

**8. 25% head-based sampling, configurable.**
`OTEL_TRACES_SAMPLER=parentbased_traceidratio` with `OTEL_TRACES_SAMPLER_ARG=0.25` as the default. Uniform random sampling was chosen over error-biased/tail sampling for simplicity — tail sampling requires buffering full traces before deciding, which needs a Collector (see Decision 1). Acceptable for v1 given personal-project traffic volume; revisit if error visibility from the missing 75% becomes a real problem.

## Risks / Trade-offs

- **[Risk]** Grafana Cloud is unreachable or slow → could add latency or resource pressure. **Mitigation**: exporters run via `BatchSpanProcessor` / `PeriodicExportingMetricReader`, both off the request/job thread with their own export timeouts; the OTel SDK catches and logs export failures internally rather than propagating them, so a Grafana Cloud outage never fails a request or job.
- **[Risk]** Auto-instrumentation captures sensitive data in span attributes (e.g. SQL parameter values, request/response bodies with tokens). **Mitigation**: use each instrumentor's default attribute set only (statement text without bound parameter values for SQLAlchemy; method/URL/status for httpx) — do not enable any "capture request/response body" or "capture headers" options.
- **[Risk]** Steady background trace/metric volume from schedulers running on fixed intervals forever, even with zero users, could approach Grafana Cloud's free-tier caps over time. **Mitigation**: 25% sampling plus low-cardinality, low-volume custom counters should stay well within free-tier limits; not actively monitored/alerted in this change — revisit if usage grows.
- **[Risk]** `pytoyoda`'s internal `hishel` HTTP cache may serve responses without an actual `httpx` call on some polls, so outbound-call span counts won't always match poll frequency 1:1. **Mitigation**: none needed — this is expected behavior, not a defect, and is worth a one-line note in code so it isn't mistaken for a bug later.
- **[Trade-off]** No local Collector means no vendor-neutral fallback — if Grafana Cloud's free tier or terms change, switching backends means reconfiguring the exporter, not just repointing a Collector. Accepted given the goal of minimal added infrastructure.

## Migration Plan

This is purely additive and inert without configuration:
1. Merge with no `OTEL_EXPORTER_OTLP_ENDPOINT` set anywhere → zero behavior change in any existing deployment (no new containers, no new required env vars, auto-instrumentation never invoked).
2. Locally or in a deployed environment, set `OTEL_EXPORTER_OTLP_ENDPOINT` + `OTEL_EXPORTER_OTLP_HEADERS` (Grafana Cloud instance ID + API token, Basic-Auth-encoded) in `.env` → observability turns on at next process start.
3. Rollback is unsetting the env var (or reverting the change) — no data migration, no schema changes, nothing stateful to unwind.

## Open Questions

- Exact span/metric naming convention (service name, span name prefixes) — will follow OTel semantic conventions where they apply (e.g. `db.*`, `http.*` are already handled by the auto-instrumentors) and a simple `mobility_manager.<component>.<action>` convention for manual spans; finalized during implementation, not blocking.
- Whether `pytoyoda`'s `hishel` caching layer needs any explicit instrumentation exclusion — to be confirmed once `HTTPXClientInstrumentor` is wired up and its span output observed against real Toyota polls.
