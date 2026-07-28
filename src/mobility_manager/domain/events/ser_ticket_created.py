"""
Domain event: SerTicketCreated.

Published exclusively by SerTicketCreationTriggerHandler when
CreateSerTicket.execute succeeds for a VehicleLocationUpdated-triggered
automatic ticket creation. CreateSerTicket itself never publishes this event,
so the manual POST /parking/ser-tickets flow is unaffected by this change —
see ser-ticket-auto-creation spec.md.

`start_date` is the created ParkingTicket's own `start_date` — the real
parking start time reported by the provider, not `created_at` (the moment
our own record was written). `end_date` is the ticket's own `end_date`. Both
are UTC-aware datetimes; SerTicketNotificationTriggerHandler converts them
into the owner's timezone before rendering a notification.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class SerTicketCreated:
    """Raised after an automatic SER ticket creation succeeds."""

    vehicle_id: UUID
    user_id: UUID
    zone_number: str
    start_date: datetime
    end_date: datetime
