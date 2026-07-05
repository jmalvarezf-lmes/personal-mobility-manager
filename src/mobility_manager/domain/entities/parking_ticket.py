"""
Domain entity: ParkingTicket.

Represents a paid parking session created through a SER ticket provider,
agnostic of the concrete city/operator implementation.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ParkingTicket:
    """Core parking ticket entity — provider-agnostic."""

    id: UUID
    vehicle_id: UUID
    user_id: UUID
    provider: str
    duration_minutes: int
    provider_reference: str | None
    created_at: datetime
