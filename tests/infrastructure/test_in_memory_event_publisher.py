"""
Unit tests for InMemoryEventPublisher.

publish() dispatches subscribed handlers asynchronously through an internal
thread pool (see add-ser-ticket-auto-creation post-implementation fix 11.2)
— these tests use `wait_for_idle()` to deterministically wait for dispatch
to finish instead of asserting immediately or sleeping.
"""

import threading

from mobility_manager.infrastructure.events.in_memory_event_publisher import (
    InMemoryEventPublisher,
)


class _EventA:
    pass


class _EventB:
    pass


def test_subscribed_handler_eventually_invoked_on_publish() -> None:
    publisher = InMemoryEventPublisher()
    received: list[_EventA] = []
    publisher.subscribe(_EventA, received.append)

    event = _EventA()
    publisher.publish(event)
    publisher.wait_for_idle()

    assert received == [event]


def test_publish_returns_before_handler_completes() -> None:
    """publish() must not block the calling thread on handler completion."""
    publisher = InMemoryEventPublisher()
    handler_started = threading.Event()
    handler_may_finish = threading.Event()

    def slow_handler(_event: _EventA) -> None:
        handler_started.set()
        handler_may_finish.wait(timeout=5.0)

    publisher.subscribe(_EventA, slow_handler)

    publisher.publish(_EventA())

    # publish() must have returned already — prove the handler is still
    # blocked on handler_may_finish, i.e. dispatch happened on another thread.
    assert handler_started.wait(timeout=5.0)
    handler_may_finish.set()
    publisher.wait_for_idle()


def test_publish_with_no_subscribers_is_a_no_op() -> None:
    publisher = InMemoryEventPublisher()
    # Should not raise, even though no handler is subscribed for _EventB.
    publisher.publish(_EventB())
    publisher.wait_for_idle()


def test_multiple_handlers_for_same_event_type_are_all_invoked() -> None:
    publisher = InMemoryEventPublisher()
    calls: list[str] = []
    lock = threading.Lock()

    def _append(value: str):
        def _handler(_event: _EventA) -> None:
            with lock:
                calls.append(value)

        return _handler

    publisher.subscribe(_EventA, _append("first"))
    publisher.subscribe(_EventA, _append("second"))

    publisher.publish(_EventA())
    publisher.wait_for_idle()

    assert sorted(calls) == ["first", "second"]


def test_handler_for_different_event_type_is_not_invoked() -> None:
    publisher = InMemoryEventPublisher()
    calls: list[str] = []
    publisher.subscribe(_EventA, lambda _e: calls.append("a"))

    publisher.publish(_EventB())
    publisher.wait_for_idle()

    assert calls == []


def test_wait_for_idle_is_a_noop_when_nothing_was_ever_published() -> None:
    publisher = InMemoryEventPublisher()
    publisher.wait_for_idle(timeout=0.1)  # must not hang or raise


def test_exception_in_handler_is_logged_and_does_not_propagate(caplog) -> None:
    publisher = InMemoryEventPublisher()

    def _raising_handler(_event: _EventA) -> None:
        raise RuntimeError("boom")

    publisher.subscribe(_EventA, _raising_handler)

    publisher.publish(_EventA())  # must not raise
    publisher.wait_for_idle()

    assert any("Unhandled exception escaped an event handler" in record.message for record in caplog.records)


def test_shutdown_stops_the_executor() -> None:
    publisher = InMemoryEventPublisher()
    publisher.shutdown(wait=True)

    assert publisher._executor._shutdown is True  # noqa: SLF001
