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

latitude/longitude/auto_created follow the same "None only for pre-existing
rows" precedent (see add-ser-ticket-history-ui design.md D1): latitude and
longitude are populated with the coordinates of the GeoLocation used to
create the ticket, and auto_created is True when created by
SerTicketCreationTriggerHandler or False when created via the manual
POST /parking/ser-tickets endpoint — the only two ticket-creation paths.
All three fields default to None only so that existing ParkingTicket(...)
call sites in concrete SerTicketProviderPort implementations (which don't
know about creation provenance) keep constructing valid entities;
CreateSerTicket.execute is the single place that fills them in with real
values before persisting, for every ticket created going forward.

start_date is the real parking start time, distinct from created_at (the
moment our own record was written). ElParkingSerTicketProvider populates it
from the steps_response's own top-level "start_time" — the moment the whole
pricing response (fare/duration options) was computed for, not wall-clock
time. Defaults to None only because ElParking is currently the only
concrete SerTicketProviderPort implementation and some call sites (tests,
other providers) construct a ParkingTicket without it; every ticket
ElParkingSerTicketProvider creates always has a real value.
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
    latitude: float | None = None
    longitude: float | None = None
    auto_created: bool | None = None
    start_date: datetime | None = None
