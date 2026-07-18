"""
Use case: DetermineSerTicketRequirement.

Decides whether a SER ticket is currently required for a vehicle located in
a given SER zone (or not in any zone at all). No longer a pure presence
check: a ticket is required only if the vehicle is inside a zone AND SER
enforcement is currently active for that zone's city (weekday hours,
calendar exceptions, and holiday status — see add-ser-enforcement-calendar
design.md D4), evaluated via the injected `SerEnforcementSchedule`
dependency.

This is deliberately modeled as its own use case rather than a bare function
or a method on SerZone, because it is the designated seam for factors that
don't exist yet in the domain: proximity to the vehicle owner's home address
(residents are often exempt near home) and a resident permit held for that
specific zone. Each of those will arrive as an injected constructor
dependency in a future change, without changing this use case's `execute`
signature or any caller's call site. Do not add placeholder parameters for
those factors now — they aren't implemented yet.
"""

from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.ports.ser_enforcement_schedule import SerEnforcementSchedule


class DetermineSerTicketRequirement:
    """Use case that decides whether a SER ticket is currently required."""

    def __init__(self, enforcement_schedule: SerEnforcementSchedule) -> None:
        self._enforcement_schedule = enforcement_schedule

    def execute(self, zone: SerZone | None) -> bool:
        """
        Return whether a ticket is currently required for `zone`.

        Returns False immediately if `zone` is None, without consulting the
        injected dependency. Otherwise, delegates to
        `enforcement_schedule.is_active_now(zone.city_code)`. No
        home-proximity or resident-permit logic is evaluated yet — see
        module docstring.
        """
        if zone is None:
            return False
        return self._enforcement_schedule.is_active_now(zone.city_code)
