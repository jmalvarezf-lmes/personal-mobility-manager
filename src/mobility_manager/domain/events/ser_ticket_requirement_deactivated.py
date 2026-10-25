"""
Domain event: SerTicketRequirementDeactivated.

Published when the computed SER ticket requirement for a vehicle transitions
from active to inactive. No handler currently consumes this event; it is
emitted for symmetry and future consumers.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from mobility_manager.domain.value_objects.ser_ticket_requirement_deactivation_reason import (
    SerTicketRequirementDeactivationReason,
)


@dataclass(frozen=True)
class SerTicketRequirementDeactivated:
    """Raised when a vehicle's SER ticket requirement becomes inactive."""

    vehicle_id: UUID
    city_code: str | None
    zone_number: str | None
    deactivated_at: datetime
    reason: SerTicketRequirementDeactivationReason
