"""
Infrastructure: InMemoryEventPublisher.

Synchronous, in-process implementation of EventPublisher. Handlers are
invoked in the same thread and process as the caller, immediately when
publish() is called. Events are not persisted or replayed — they are lost
on process restart and don't cross multiple app instances. Acceptable for
a single-instance deployment; the port boundary is what makes swapping to a
durable/distributed adapter later a contained change.
"""

from collections import defaultdict
from collections.abc import Callable
from typing import Any

from mobility_manager.domain.ports.event_publisher import EventPublisher


class InMemoryEventPublisher(EventPublisher):
    """In-memory, synchronous pub/sub dispatcher for domain events."""

    def __init__(self) -> None:
        self._handlers: dict[type, list[Callable[[Any], None]]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: Callable[[Any], None]) -> None:
        """Register a handler to be invoked whenever an event of event_type is published.

        `handler` may be typed to accept the specific event subclass (e.g.
        `Callable[[VehicleLocationUpdated], None]`) rather than `object` — the
        `Any` parameter type here exists so mypy allows narrower handler
        signatures without a contravariance complaint, while `publish` still
        only ever calls it with an instance of `event_type`.
        """
        self._handlers[event_type].append(handler)

    def publish(self, event: object) -> None:
        """Synchronously invoke every handler subscribed to type(event).

        No-op if no handler is subscribed for that event type.
        """
        for handler in self._handlers.get(type(event), []):
            handler(event)
