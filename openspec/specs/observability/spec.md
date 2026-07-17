### Requirement: Inbound HTTP requests are traced
The system SHALL automatically create a trace span for every inbound HTTP request handled by the FastAPI application when observability is active.

#### Scenario: Request handled while observability is active
- **WHEN** an OTLP endpoint is configured and a client sends a request to any API route
- **THEN** a span representing that request is created and exported, including route, method, and status code

### Requirement: Outbound HTTP calls are traced
The system SHALL automatically create a trace span for every outbound `httpx` call to an external provider (Madrid SER, ElParking, Google OAuth, Toyota) when observability is active.

#### Scenario: Call to an external provider during an active trace
- **WHEN** application code makes an outbound `httpx` call while a parent span is active (a request, a scheduler job, or an event handler dispatch)
- **THEN** a child span for the outbound call is created, capturing method, URL, and response status, and is exported as part of the same trace

### Requirement: Database queries are traced
The system SHALL automatically create a trace span for queries executed against the shared SQLAlchemy `Engine` when observability is active.

#### Scenario: Query executed within an active trace
- **WHEN** a repository executes a query against the Postgres engine while a parent span is active
- **THEN** a child span for that query is created, capturing the statement text but not bound parameter values, and is exported as part of the same trace

### Requirement: Scheduled job runs are traced independently of request context
The system SHALL create a root trace span for each scheduler job run (`ParkingIngestionScheduler`, `VehicleLocationScheduler`), since these run outside any HTTP request context.

#### Scenario: Scheduler job executes on its interval
- **WHEN** a scheduled job run starts, whether or not any HTTP request is in flight
- **THEN** a new root span is created for that job run and exported, covering the full duration of the run

#### Scenario: Scheduler job run fails
- **WHEN** a scheduled job run raises an exception that is caught by the job's existing error handling
- **THEN** the job's root span records the exception and is marked as an error, and the job's existing swallow-and-continue behavior is otherwise unchanged

### Requirement: Event handler dispatch is traced independently of request context
The system SHALL create a root trace span for each event handler invocation (`NotificationDispatchHandler`, `SerTicketTriggerHandler`), since these run synchronously outside any HTTP request context.

#### Scenario: Event handler invoked via the in-memory event publisher
- **WHEN** `InMemoryEventPublisher.publish()` invokes a subscribed handler
- **THEN** a new root span is created for that handler invocation and exported, covering the full duration of the handler's execution

#### Scenario: Event handler execution fails
- **WHEN** a handler invocation raises an exception that is caught by the handler's existing error handling
- **THEN** the handler's root span records the exception and is marked as an error, and the handler's existing swallow-and-continue behavior is otherwise unchanged

### Requirement: Custom business metrics are recorded via a centralized module
The system SHALL expose a centralized metrics module that pre-registers named counter instruments and typed recording functions for notification dispatch outcomes, ingestion run outcomes, and vehicle poll outcomes.

#### Scenario: Notification dispatch outcome recorded
- **WHEN** `NotificationDispatchHandler` completes an attempt to send a notification through a channel
- **THEN** the notification dispatch counter is incremented with the channel name and a success/failure label

#### Scenario: Ingestion run outcome recorded
- **WHEN** a parking data ingestion run for a city completes or fails
- **THEN** the ingestion counter is incremented with the city name and a success/failure label

#### Scenario: Vehicle poll outcome recorded
- **WHEN** `VehicleLocationScheduler` completes a poll of a vehicle's location
- **THEN** the vehicle poll counter is incremented with a success/failure label

#### Scenario: A new custom metric is added later
- **WHEN** a developer needs to record a new business metric
- **THEN** they add one instrument registration and one recording function to the metrics module, without modifying OpenTelemetry SDK initialization or auto-instrumentation wiring

### Requirement: Telemetry export is via OTLP to a configurable endpoint
The system SHALL export traces and metrics using OTLP/HTTP to an endpoint and credentials read from standard OpenTelemetry environment variables.

#### Scenario: Endpoint configured
- **WHEN** `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS` are set in the environment
- **THEN** the application initializes real trace and metric providers at startup and exports collected spans and metrics to that endpoint

### Requirement: Observability is inactive when no endpoint is configured
The system SHALL run with no telemetry collection, no auto-instrumentation, and no export overhead when `OTEL_EXPORTER_OTLP_ENDPOINT` is not set, and SHALL NOT fail to start because of missing OpenTelemetry configuration.

#### Scenario: No endpoint configured
- **WHEN** the application starts without `OTEL_EXPORTER_OTLP_ENDPOINT` set
- **THEN** the application starts normally, all tracing and metrics calls in application code are no-ops, and no data is sent to any telemetry backend

### Requirement: No log telemetry is exported
The system SHALL NOT export application logs via OpenTelemetry under any configuration.

#### Scenario: Observability is active
- **WHEN** an OTLP endpoint is configured and the application is running
- **THEN** only trace and metric signals are exported; no log records are sent via OTLP

### Requirement: Telemetry excludes personally identifiable information
The system SHALL restrict custom metric labels and manually-created span attributes to bounded, non-identifying values, and SHALL NOT include user identifiers, vehicle plate numbers, email addresses, or other free-text personal data as metric labels or manual span attributes.

#### Scenario: Recording a notification dispatch metric
- **WHEN** a notification dispatch outcome is recorded
- **THEN** the only labels attached are the channel name and a success/failure flag, with no recipient identifier included

### Requirement: Trace sampling rate is configurable
The system SHALL sample traces at a default rate of 25%, overridable via standard OpenTelemetry sampler environment variables.

#### Scenario: Default sampling
- **WHEN** observability is active and no sampler environment variables are set
- **THEN** approximately 25% of traces are sampled and exported

#### Scenario: Overridden sampling
- **WHEN** `OTEL_TRACES_SAMPLER_ARG` is set to a different ratio
- **THEN** traces are sampled at that configured ratio instead of the default

### Requirement: Telemetry export failures do not affect application behavior
The system SHALL NOT allow a failure or delay in exporting telemetry to affect the outcome or latency of the HTTP request, scheduler job, or event handler that produced it.

#### Scenario: Telemetry backend is unreachable
- **WHEN** the configured OTLP endpoint is unreachable or times out
- **THEN** the request, scheduler job, or event handler that produced the telemetry completes normally and unaffected, and the export failure is only observable in application logs
