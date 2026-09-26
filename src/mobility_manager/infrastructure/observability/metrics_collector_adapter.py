"""
Infrastructure adapter: OpenTelemetryMetricsCollector.

Implements the domain MetricsCollector port by delegating to the existing
infrastructure metrics module, which wraps the OpenTelemetry SDK.
"""

from mobility_manager.domain.ports.metrics_collector import MetricsCollector
from mobility_manager.infrastructure.observability.metrics import (
    record_ambient_label_lookup,
    record_notification_dispatch,
    record_ser_ticket_auto_creation,
)


class OpenTelemetryMetricsCollector(MetricsCollector):
    """Forward metric recordings to the OpenTelemetry instruments."""

    def record_notification_dispatch(self, channel: str, success: bool) -> None:
        record_notification_dispatch(channel=channel, success=success)

    def record_ambient_label_lookup(self, status: str) -> None:
        record_ambient_label_lookup(status=status)

    def record_ser_ticket_auto_creation(self, outcome: str) -> None:
        record_ser_ticket_auto_creation(outcome=outcome)
