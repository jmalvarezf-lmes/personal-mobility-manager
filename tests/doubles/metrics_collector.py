"""Test double for the MetricsCollector domain port."""

from mobility_manager.domain.ports.metrics_collector import MetricsCollector


class FakeMetricsCollector(MetricsCollector):
    """Records metric calls in memory for assertions."""

    def __init__(self) -> None:
        self.notification_dispatches: list[dict[str, object]] = []
        self.ambient_label_lookups: list[str] = []
        self.ser_ticket_auto_creations: list[str] = []

    def record_notification_dispatch(self, channel: str, success: bool) -> None:
        self.notification_dispatches.append({"channel": channel, "success": success})

    def record_ambient_label_lookup(self, status: str) -> None:
        self.ambient_label_lookups.append(status)

    def record_ser_ticket_auto_creation(self, outcome: str) -> None:
        self.ser_ticket_auto_creations.append(outcome)
