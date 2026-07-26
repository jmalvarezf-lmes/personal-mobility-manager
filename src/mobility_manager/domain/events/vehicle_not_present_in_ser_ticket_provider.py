"""
Domain event: VehicleNotPresentInSerTicketProvider.

Published by CreateSerTicket when the provider's create_ticket raises
SerProviderVehicleNotFoundError — the vehicle's license plate could not be
matched against the SER ticket provider's own vehicle records. No handler is
registered for this event in this change, mirroring how VehicleLocationUpdated
shipped before SerTicketNotificationTriggerHandler existed.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class VehicleNotPresentInSerTicketProvider:
    """Raised (as an event, not an exception) when a vehicle can't be matched on a SER ticket provider's side."""

    vehicle_id: UUID
    user_id: UUID
    provider: str
