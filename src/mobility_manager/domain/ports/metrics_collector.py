"""
Domain port: MetricsCollector.

Application-layer code records business metrics through this port so it never
imports infrastructure observability libraries. Infrastructure provides an
adapter that forwards calls to the real OTel instruments.
"""

from abc import ABC, abstractmethod


class MetricsCollector(ABC):
    """Record application-level business metrics."""

    @abstractmethod
    def record_notification_dispatch(self, channel: str, success: bool) -> None:
        """Record one notification dispatch attempt through `channel`."""

    @abstractmethod
    def record_ambient_label_lookup(self, status: str) -> None:
        """Record one DGT ambient label lookup attempt with resulting `status`."""

    @abstractmethod
    def record_ser_ticket_auto_creation(self, outcome: str) -> None:
        """Record one automatic SER ticket creation attempt with `outcome`."""
