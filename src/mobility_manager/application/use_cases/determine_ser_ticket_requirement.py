"""
Use case: DetermineSerTicketRequirement.

Decides whether a SER ticket is currently required for a vehicle located in
a given SER zone (or not in any zone at all). A ticket is required only if
the vehicle is inside a zone AND SER enforcement is currently active for
that zone's city (weekday hours, calendar exceptions, and holiday status —
see add-ser-enforcement-calendar design.md D4), evaluated via the injected
`SerEnforcementSchedule` dependency, AND the vehicle either has no stored
exemption matching the zone's `(city_code, zone_number)` (see
add-vehicle-ser-parking-exemption design.md D4), or its matching exemption's
zone fails the injected `SerExemptionZoneRule` dependency's
`is_zone_eligible(zone)` check (see add-ser-exemption-zone-rule design.md —
e.g. Madrid requires the zone to be green ("Verde") for the exemption to
actually apply). This use case stays city-agnostic: it never names Madrid
or any zone-type string itself, delegating that per-city fact entirely to
the injected zone rule. The zone rule is only consulted once a matching
exemption is confirmed, preserving the cheapest-check-first ordering.

This is deliberately modeled as its own use case rather than a bare function
or a method on SerZone, because it is the designated seam for factors that
don't exist yet in the domain: proximity to the vehicle owner's home address
(residents are often exempt near home) remains an unevaluated seam for a
future change.

`execute()`'s signature grew a required `vehicle_id: UUID` parameter to
support the per-vehicle exemption check — this supersedes this use case's
former "no signature change" seam (see add-vehicle-ser-parking-exemption
design.md Context: a per-vehicle fact cannot be answered by a
constructor-injected dependency alone). The enforcement-schedule check
still runs first and short-circuits before the exemption repository is
consulted at all, preserving the original cheapest-check-first ordering.

`execute()` also grew a required `at: datetime` parameter (see
add-ser-ticket-auto-creation's post-implementation fix 11.1): after the
enforcement-schedule check and before the exemption check, this use case
now short-circuits to `False` (not required) if the vehicle already has an
active ParkingTicket at `at`, via the injected `ParkingTicketRepository`.
This closes an idempotency gap where a fast-repeating VehicleLocationUpdated
stream could otherwise trigger more than one real (paid) ticket creation for
the same vehicle while a ticket it already holds is still valid. The check
is deliberately vehicle-scoped, not zone-scoped — ParkingTicket does not
store a zone number today, so a vehicle with any active ticket anywhere is
treated as not requiring a new one; adding a zone column is out of scope for
this fix.
"""

from datetime import datetime
from uuid import UUID

from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.ports.parking_ticket_repository import (
    ParkingTicketRepository,
)
from mobility_manager.domain.ports.ser_enforcement_schedule import SerEnforcementSchedule
from mobility_manager.domain.ports.ser_exemption_zone_rule import SerExemptionZoneRule
from mobility_manager.domain.ports.vehicle_ser_parking_exemption_repository import (
    VehicleSerParkingExemptionRepository,
)


class DetermineSerTicketRequirement:
    """Use case that decides whether a SER ticket is currently required."""

    def __init__(
        self,
        enforcement_schedule: SerEnforcementSchedule,
        exemption_repo: VehicleSerParkingExemptionRepository,
        exemption_zone_rule: SerExemptionZoneRule,
        ticket_repo: ParkingTicketRepository,
    ) -> None:
        self._enforcement_schedule = enforcement_schedule
        self._exemption_repo = exemption_repo
        self._exemption_zone_rule = exemption_zone_rule
        self._ticket_repo = ticket_repo

    def execute(self, zone: SerZone | None, vehicle_id: UUID, at: datetime) -> bool:
        """
        Return whether a ticket is currently required for `vehicle_id` in `zone`.

        Returns False immediately if `zone` is None, without consulting any
        injected dependency. Otherwise, returns False if the injected
        enforcement-schedule dependency's `is_active_now(zone.city_code)`
        returns False, without consulting the ticket repository, the
        exemption repository, or the zone rule. Otherwise, returns False if
        `vehicle_id` already has an active ParkingTicket at `at` (see module
        docstring), without consulting the exemption repository or the zone
        rule. Otherwise, looks up the vehicle's stored exemption; if it does
        not match `(zone.city_code, zone.zone_number)`, returns True without
        consulting the zone rule. Otherwise (a matching exemption exists),
        returns False only if the injected `SerExemptionZoneRule`
        dependency's `is_zone_eligible(zone)` returns True. No
        home-proximity logic is evaluated yet — see module docstring.
        """
        if zone is None:
            return False
        if not self._enforcement_schedule.is_active_now(zone.city_code):
            return False
        if self._ticket_repo.find_active_for_vehicle(vehicle_id, at) is not None:
            return False
        exemption = self._exemption_repo.find_by_vehicle_id(vehicle_id)
        if exemption is None or (exemption.city_code, exemption.zone_number) != (
            zone.city_code,
            zone.zone_number,
        ):
            return True
        return not self._exemption_zone_rule.is_zone_eligible(zone)
