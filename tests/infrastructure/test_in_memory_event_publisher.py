"""
Unit tests for InMemoryEventPublisher.
"""

from mobility_manager.infrastructure.events.in_memory_event_publisher import (
    InMemoryEventPublisher,
)


class _EventA:
    pass


class _EventB:
    pass


def test_subscribed_handler_invoked_synchronously_on_publish() -> None:
    publisher = InMemoryEventPublisher()
    received: list[_EventA] = []
    publisher.subscribe(_EventA, received.append)

    event = _EventA()
    publisher.publish(event)

    assert received == [event]


def test_publish_with_no_subscribers_is_a_no_op() -> None:
    publisher = InMemoryEventPublisher()
    # Should not raise, even though no handler is subscribed for _EventB.
    publisher.publish(_EventB())


def test_multiple_handlers_for_same_event_type_are_all_invoked() -> None:
    publisher = InMemoryEventPublisher()
    calls: list[str] = []
    publisher.subscribe(_EventA, lambda _e: calls.append("first"))
    publisher.subscribe(_EventA, lambda _e: calls.append("second"))

    publisher.publish(_EventA())

    assert calls == ["first", "second"]


def test_handler_for_different_event_type_is_not_invoked() -> None:
    publisher = InMemoryEventPublisher()
    calls: list[str] = []
    publisher.subscribe(_EventA, lambda _e: calls.append("a"))

    publisher.publish(_EventB())

    assert calls == []
