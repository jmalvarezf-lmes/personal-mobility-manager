"""
Domain event: SerTicketRequirementActivated.

Published when the computed SER ticket requirement for a vehicle transitions
from inactive to active.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class SerTicketRequirementActivated:
    """Raised when a vehicle's SER ticket requirement becomes active."""

    vehicle_id: UUID
    city_code: str | None
    zone_number: str | None
    latitude: float
    longitude: float
    activated_at: datetime
