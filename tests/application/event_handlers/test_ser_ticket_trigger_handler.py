"""
Unit test for SerTicketTriggerHandler.

The handler is intentionally a no-op in this change (scaffolding for a future
"check SER zone + user preference + maybe create a ticket" flow). There is
nothing observable to assert beyond "handling an event doesn't raise" — this
test is deliberately minimal and exists to guard against a future accidental
regression turning this into something that raises on a well-formed event.
"""

from datetime import UTC, datetime
from uuid import uuid4

from mobility_manager.application.event_handlers.ser_ticket_trigger_handler import (
    SerTicketTriggerHandler,
)
from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)


def test_handle_does_not_raise_and_has_no_observable_side_effects() -> None:
    handler = SerTicketTriggerHandler()
    event = VehicleLocationUpdated(
        vehicle_id=uuid4(),
        latitude=40.4168,
        longitude=-3.7038,
        recorded_at=datetime.now(UTC),
        received_at=datetime.now(UTC),
        source="push",
    )

    result = handler.handle(event)

    assert result is None
