"""
Port (interface): EventPublisher.

Abstract contract for publishing domain events. The signature intentionally
does not assume a synchronous or asynchronous transport, so a future
message-broker-backed adapter can replace the in-memory one without any
caller needing to change.
"""

from abc import ABC, abstractmethod


class EventPublisher(ABC):
    """Abstract publisher for domain events."""

    @abstractmethod
    def publish(self, event: object) -> None:
        """Publish a domain event to all interested subscribers."""
        ...
