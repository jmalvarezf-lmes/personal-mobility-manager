"""
Application event handler: NotificationDispatchHandler.

Registered against VehicleLocationUpdated at application startup. Scaffolding
for a future "decide whether/what to notify the user about" flow —
deliberately a no-op in this change, exactly mirroring
SerTicketTriggerHandler's exact pattern. Behavior will be widened little by
little in follow-up changes; do not add user preference reads or
SendNotification calls here yet.
"""

from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)


class NotificationDispatchHandler:
    """No-op subscriber for VehicleLocationUpdated — scaffolding only."""

    def handle(self, event: VehicleLocationUpdated) -> None:
        """Handle a VehicleLocationUpdated event.

        Intentionally a no-op in this change: no user preference lookup, no
        SendNotification call.
        """
        pass
