"""
Domain event: SerTicketCreationFailed.

Published exclusively by SerTicketCreationTriggerHandler when
CreateSerTicket.execute raises for a VehicleLocationUpdated-triggered
automatic ticket creation attempt — see ser-ticket-auto-creation spec.md.

`reason` is a small closed-vocabulary string derived from the exception
type — never the raw exception message or `str(exc)` — e.g.
"no_provider_session", "no_provider_connected", "vehicle_not_matched",
"zone_not_found", "provider_error". It exists purely for future
observability/metrics consumers: SerTicketNotificationTriggerHandler's
`ser_ticket_creation_failed` notification never interpolates it into
user-facing text (see design.md decision 2).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class SerTicketCreationFailed:
    """Raised after an automatic SER ticket creation attempt fails."""

    vehicle_id: UUID
    user_id: UUID
    zone_number: str
    reason: str
