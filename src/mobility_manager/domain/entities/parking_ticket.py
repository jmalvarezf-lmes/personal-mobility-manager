"""
Domain entity: ParkingTicket.

Represents a paid parking session created through a SER ticket provider,
agnostic of the concrete city/operator implementation.

city_code/zone_number identify the SER zone this ticket was created for —
the same (city_code, zone_number) identity pair SerZone and
VehicleSerParkingExemption use for their own zone fields. Both are `None`
only for tickets persisted before these fields existed (see
change-ser-auto-ticket-zone-gate design.md D4): there is no reliable way to
recover which zone an already-created ticket was for after the fact, so
those legacy rows keep both fields `None` rather than being backfilled.
DetermineSerTicketRequirement treats a `(None, None)` ticket as a fail-safe
that unconditionally suppresses new ticket creation for that vehicle (see
design.md D5).
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
    cost: float
    end_date: datetime
    created_at: datetime
    city_code: str | None
    zone_number: str | None
