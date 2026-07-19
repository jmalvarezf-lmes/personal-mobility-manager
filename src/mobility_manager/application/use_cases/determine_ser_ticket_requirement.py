"""
Use case: DetermineSerTicketRequirement.

Decides whether a SER ticket is currently required for a vehicle located in
a given SER zone (or not in any zone at all). A ticket is required only if
the vehicle is inside a zone AND SER enforcement is currently active for
that zone's city (weekday hours, calendar exceptions, and holiday status —
see add-ser-enforcement-calendar design.md D4), evaluated via the injected
`SerEnforcementSchedule` dependency, AND the vehicle has no stored
exemption matching the zone's `(city_code, zone_number)` (see
add-vehicle-ser-parking-exemption design.md D4).

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
"""

from uuid import UUID

from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.ports.ser_enforcement_schedule import SerEnforcementSchedule
from mobility_manager.domain.ports.vehicle_ser_parking_exemption_repository import (
    VehicleSerParkingExemptionRepository,
)


class DetermineSerTicketRequirement:
    """Use case that decides whether a SER ticket is currently required."""

    def __init__(
        self,
        enforcement_schedule: SerEnforcementSchedule,
        exemption_repo: VehicleSerParkingExemptionRepository,
    ) -> None:
        self._enforcement_schedule = enforcement_schedule
        self._exemption_repo = exemption_repo

    def execute(self, zone: SerZone | None, vehicle_id: UUID) -> bool:
        """
        Return whether a ticket is currently required for `vehicle_id` in `zone`.

        Returns False immediately if `zone` is None, without consulting
        either injected dependency. Otherwise, returns False if the
        injected enforcement-schedule dependency's
        `is_active_now(zone.city_code)` returns False, without consulting
        the exemption repository. Otherwise, looks up the vehicle's stored
        exemption; if it matches `(zone.city_code, zone.zone_number)`,
        returns False. Otherwise returns True. No home-proximity logic is
        evaluated yet — see module docstring.
        """
        if zone is None:
            return False
        if not self._enforcement_schedule.is_active_now(zone.city_code):
            return False
        exemption = self._exemption_repo.find_by_vehicle_id(vehicle_id)
        return exemption is None or (exemption.city_code, exemption.zone_number) != (
            zone.city_code,
            zone.zone_number,
        )
