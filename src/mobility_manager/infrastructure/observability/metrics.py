"""
Infrastructure: centralized custom business metrics.

Pre-registers every counter instrument at module load time via
metrics.get_meter("mobility_manager") — safe to do even before (or without)
init_observability() ever registering a real MeterProvider, since
metrics.get_meter() returns a proxy that becomes bound to whichever provider
is set later (see setup.py's module docstring). Call sites never touch the
raw OTel metrics API directly.

Extension pattern (see design.md decision 5): adding a new metric later is
one `create_counter`/`create_histogram` call here plus one typed recording
function below — no changes to SDK init or auto-instrumentation wiring in
setup.py are ever needed.

Every recording function below takes typed, bounded parameters only (never
a generic **attributes passthrough) — this is what enforces design.md
decision 7 / the "Telemetry excludes personally identifiable information"
requirement: labels are restricted to small, closed-set values (channel
name, city name, success boolean), never a user id, plate number, email, or
other free-text value.
"""

from opentelemetry import metrics

_meter = metrics.get_meter("mobility_manager")

_notification_dispatch_counter = _meter.create_counter(
    name="mobility_manager.notification_dispatch",
    unit="1",
    description="Count of notification dispatch attempts, labeled by channel and outcome.",
)

_ingestion_run_counter = _meter.create_counter(
    name="mobility_manager.ingestion_run",
    unit="1",
    description="Count of parking data ingestion runs, labeled by city and outcome.",
)

_vehicle_poll_counter = _meter.create_counter(
    name="mobility_manager.vehicle_poll",
    unit="1",
    description="Count of vehicle location poll attempts, labeled by outcome.",
)


def record_notification_dispatch(channel: str, success: bool) -> None:
    """Record one notification dispatch attempt through `channel`."""
    _notification_dispatch_counter.add(1, {"channel": channel, "success": success})


def record_ingestion_run(city: str, success: bool) -> None:
    """Record one parking data ingestion run for `city`."""
    _ingestion_run_counter.add(1, {"city": city, "success": success})


def record_vehicle_poll(success: bool) -> None:
    """Record one vehicle location poll attempt."""
    _vehicle_poll_counter.add(1, {"success": success})
