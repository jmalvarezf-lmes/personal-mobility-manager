"""
Unit test for NotificationDispatchHandler.

The handler is intentionally a no-op in this change (scaffolding for a
future "decide whether/what to notify the user about" flow). There is
nothing observable to assert beyond "handling an event doesn't raise" —
mirrors test_ser_ticket_trigger_handler.py's documented-minimalism style.
"""

from datetime import UTC, datetime
from uuid import uuid4

from mobility_manager.application.event_handlers.notification_dispatch_handler import (
    NotificationDispatchHandler,
)
from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)


def test_handle_does_not_raise_and_has_no_observable_side_effects() -> None:
    handler = NotificationDispatchHandler()
    event = VehicleLocationUpdated(
        vehicle_id=uuid4(),
        latitude=40.4168,
        longitude=-3.7038,
        recorded_at=datetime.now(UTC),
        source="push",
    )

    result = handler.handle(event)

    assert result is None
