"""
Application event handler: SerTicketTriggerHandler.

Registered against VehicleLocationUpdated at application startup. Scaffolding
for a future "check SER zone + user preference + maybe create a ticket" flow
— deliberately a no-op in this change. Behavior will be widened little by
little in follow-up changes; do not add SER zone lookups, user preference
reads, or ticket-creation triggering logic here yet.
"""

from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)


class SerTicketTriggerHandler:
    """No-op subscriber for VehicleLocationUpdated — scaffolding only."""

    def handle(self, event: VehicleLocationUpdated) -> None:
        """Handle a VehicleLocationUpdated event.

        Intentionally a no-op in this change: no SER zone lookup, no user
        preference lookup, no ticket creation.
        """
        pass
