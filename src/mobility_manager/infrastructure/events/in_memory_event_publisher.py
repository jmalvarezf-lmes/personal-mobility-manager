"""
Infrastructure: InMemoryEventPublisher.

In-process implementation of EventPublisher. Handlers are dispatched
asynchronously through a small internal `concurrent.futures.ThreadPoolExecutor`
(see add-ser-ticket-auto-creation post-implementation fix 11.2): `publish()`
submits one task per subscribed handler and returns immediately, without
waiting for any handler to finish. This matters for callers on a request
path — e.g. the push-location HTTP endpoint — that would otherwise block for
as long as the slowest handler takes (up to ~85s when a handler makes a
provider HTTP call), even though the event's own effect (e.g. the vehicle
location) was already durably persisted before publish() was called.

Each handler already wraps its own body in a broad try/except (see the
sibling event-handler modules' docstrings), so an exception should never
reach this publisher. As a purely defensive backstop, any exception that
still escapes a handler is logged via `future.add_done_callback` — never
silently dropped — but it does not propagate to the calling thread and does
not affect any other handler's dispatch (each handler now runs as an
independent thread-pool task, so there is no shared "loop" for one handler's
failure to interrupt).

Events are not persisted or replayed — they are lost on process restart and
don't cross multiple app instances. Acceptable for a single-instance
deployment; the port boundary is what makes swapping to a durable/distributed
adapter later a contained change.

`wait_for_idle()` is a test-only synchronization helper: it blocks until
every handler dispatched so far by this instance has finished, so tests can
assert on a handler's effect deterministically instead of sleeping.
`shutdown()` stops accepting new dispatches and is called from the
application lifespan's shutdown block, alongside the other schedulers.
"""

import concurrent.futures
import logging
import threading
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from mobility_manager.domain.ports.event_publisher import EventPublisher

logger = logging.getLogger(__name__)

_DEFAULT_MAX_WORKERS = 4


class InMemoryEventPublisher(EventPublisher):
    """In-memory, asynchronously-dispatched pub/sub dispatcher for domain events."""

    def __init__(self, max_workers: int = _DEFAULT_MAX_WORKERS) -> None:
        self._handlers: dict[type, list[Callable[[Any], None]]] = defaultdict(list)
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="event-publisher"
        )
        self._lock = threading.Lock()
        self._pending: set[concurrent.futures.Future[None]] = set()

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
        """Asynchronously dispatch every handler subscribed to type(event).

        Submits one task per subscribed handler to the internal thread pool
        and returns immediately — this method never blocks on a handler's
        completion. No-op if no handler is subscribed for that event type.
        """
        for handler in self._handlers.get(type(event), []):
            future: concurrent.futures.Future[None] = self._executor.submit(handler, event)
            with self._lock:
                self._pending.add(future)
            future.add_done_callback(self._on_handler_done)

    def _on_handler_done(self, future: concurrent.futures.Future[None]) -> None:
        with self._lock:
            self._pending.discard(future)
        exc = future.exception()
        if exc is not None:
            # Defensive only: every handler already self-contains its own
            # exceptions (see module docstring) — this must never be the
            # primary error-handling path, only a backstop so nothing
            # vanishes silently if that ever stops being true.
            logger.error("Unhandled exception escaped an event handler", exc_info=exc)

    def wait_for_idle(self, timeout: float = 5.0) -> None:
        """
        Test-only helper: block until every handler dispatched so far by
        this instance has finished (or `timeout` seconds have elapsed).

        Not part of the EventPublisher port — callers needing deterministic
        test synchronization should depend on the concrete
        InMemoryEventPublisher type directly.
        """
        with self._lock:
            pending = list(self._pending)
        concurrent.futures.wait(pending, timeout=timeout)

    def shutdown(self, wait: bool = True) -> None:
        """Stop accepting new dispatches, called from the application lifespan's shutdown block."""
        self._executor.shutdown(wait=wait)
