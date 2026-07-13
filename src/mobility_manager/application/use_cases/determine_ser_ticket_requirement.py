"""
Use case: DetermineSerTicketRequirement.

Decides whether a SER ticket is currently required for a vehicle located in
a given SER zone (or not in any zone at all). Today this is a pure presence
check: a ticket is required if and only if the vehicle is inside a zone.

This is deliberately modeled as its own use case rather than a bare function
or a method on SerZone, because it is the designated seam for factors that
don't exist yet in the domain: proximity to the vehicle owner's home address
(residents are often exempt near home), a resident permit held for that
specific zone, and the zone's enforcement hours/timetable (SER zones aren't
ticketable 24/7). Each of those will arrive as an injected constructor
dependency in a future change, without changing this use case's `execute`
signature or any caller's call site. Do not add placeholder parameters for
those factors now — they aren't implemented yet.
"""

from mobility_manager.domain.entities.ser_zone import SerZone


class DetermineSerTicketRequirement:
    """Use case that decides whether a SER ticket is currently required."""

    def execute(self, zone: SerZone | None) -> bool:
        """
        Return whether a ticket is currently required for `zone`.

        A pure presence check for now: True if `zone` is not None, False
        otherwise. No enforcement-hours, home-proximity, or resident-permit
        logic is evaluated yet — see module docstring.
        """
        return zone is not None
