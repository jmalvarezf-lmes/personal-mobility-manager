"""
Use case: DetermineSerTicketRequirement.

Decides whether a SER ticket is currently required for a vehicle located in
a given SER zone (or not in any zone at all). A ticket is required only if
the vehicle is inside a zone AND SER enforcement is currently active for
that zone's city (weekday hours, calendar exceptions, and holiday status —
see add-ser-enforcement-calendar design.md D4), evaluated via the injected
`SerEnforcementSchedule` dependency, AND the vehicle is not exempt via
either of two independent OR paths: its ambient label (see below), or a
stored manual exemption whose zone passes the injected `SerExemptionZoneRule`
dependency's `is_zone_eligible(zone)` check (see add-ser-exemption-zone-rule
design.md — e.g. Madrid requires the zone to be green ("Verde") for the
exemption to actually apply). This use case stays city-agnostic: it never
names Madrid or any zone-type/label string itself, delegating those
per-city facts entirely to the injected zone rule and label-exemption rule.
The zone rule is only consulted once a matching exemption is confirmed,
preserving the cheapest-check-first ordering.

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
the same vehicle while a ticket it already holds is still valid.

This active-ticket short-circuit is zone-aware (see
change-ser-auto-ticket-zone-gate design.md D5): a `ParkingTicket` now carries
the `(city_code, zone_number)` of the zone it was created for. It calls
`ParkingTicketRepository.find_all_active_for_vehicle(vehicle_id, at)`, which
returns *every* one of the vehicle's tickets still active at `at`, not just a
single one — a vehicle can legitimately hold more than one concurrently-
active ticket, one per SER zone it has entered while a previous zone's
ticket has not yet expired (e.g. zone A -> zone B while A's ticket is still
valid -> back to zone A while both are still valid). It short-circuits to
`False` immediately if **any** ticket in that list either has `(city_code,
zone_number) == (None, None)` (a legacy ticket persisted before these fields
existed — its real zone can't be recovered, so it is treated, fail-safe, as
covering any zone; better to under-create than risk a duplicate paid
ticket) or matches `(zone.city_code, zone.zone_number)` (already covered by
that specific ticket). If no ticket in the list satisfies either condition
(including when the list is empty), the active-ticket check does NOT
short-circuit — it falls through to the ambient-label/exemption chain below
exactly as if the vehicle had no active tickets at all.

A post-implementation 4R review found that comparing the current zone
against only a single, most-recent-by-`end_date` ticket (the original
`find_active_for_vehicle` contract) was unsafe: this change is precisely
what makes it possible for a vehicle to hold multiple concurrently-active
tickets in different zones for the first time (previously any active ticket
blocked all creation, so at most one could ever be active — that invariant
made the single-row query safe, and this change deliberately breaks it). A
vehicle cycling zone A -> zone B -> zone A while both tickets are still
valid would have the zone-A check compare against ticket B (typically the
one with the later `end_date`, since it was created after A with a similar
duration) — the mismatch would fail to short-circuit and create a
duplicate, real, paid third ticket for zone A even though ticket A was still
valid. Checking every active ticket, not just one, closes this gap.

This use case gained a second, independent exemption path (see
add-ser-label-exemption-rule design.md): after the active-ticket
short-circuit and before the manual-exemption check, it looks up the
vehicle's `VehicleAmbientLabel` via the injected `VehicleAmbientLabelRepository`
dependency. If the lookup's `status == AmbientLabelStatus.FOUND` and the
injected `SerLabelExemptionRule` dependency's `is_label_exempt(zone.city_code,
label)` returns True (e.g. a confirmed electric, label "0", vehicle), this use
case returns False immediately, without consulting the manual-exemption
repository or the zone rule at all — the two exemption paths are independent
ORs, not merged into one. Any other ambient-label outcome — no row (`None`),
or a row whose status is `NOT_FOUND` or `ERROR` — is a deliberate fail-safe:
an unresolved lookup must never be treated as proof of an electric label, so
it falls through unchanged to the existing manual-exemption logic instead of
itself producing a True or False answer.
"""

from datetime import datetime
from uuid import UUID

from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.ports.parking_ticket_repository import (
    ParkingTicketRepository,
)
from mobility_manager.domain.ports.ser_enforcement_schedule import SerEnforcementSchedule
from mobility_manager.domain.ports.ser_exemption_zone_rule import SerExemptionZoneRule
from mobility_manager.domain.ports.ser_label_exemption_rule import SerLabelExemptionRule
from mobility_manager.domain.ports.vehicle_ambient_label_repository import (
    VehicleAmbientLabelRepository,
)
from mobility_manager.domain.ports.vehicle_ser_parking_exemption_repository import (
    VehicleSerParkingExemptionRepository,
)
from mobility_manager.domain.value_objects.ambient_label_status import AmbientLabelStatus


class DetermineSerTicketRequirement:
    """Use case that decides whether a SER ticket is currently required."""

    def __init__(
        self,
        enforcement_schedule: SerEnforcementSchedule,
        exemption_repo: VehicleSerParkingExemptionRepository,
        exemption_zone_rule: SerExemptionZoneRule,
        ticket_repo: ParkingTicketRepository,
        ambient_label_repo: VehicleAmbientLabelRepository,
        label_exemption_rule: SerLabelExemptionRule,
    ) -> None:
        self._enforcement_schedule = enforcement_schedule
        self._exemption_repo = exemption_repo
        self._exemption_zone_rule = exemption_zone_rule
        self._ticket_repo = ticket_repo
        self._ambient_label_repo = ambient_label_repo
        self._label_exemption_rule = label_exemption_rule

    def execute(self, zone: SerZone | None, vehicle_id: UUID, at: datetime) -> bool:
        """
        Return whether a ticket is currently required for `vehicle_id` in `zone`.

        Returns False immediately if `zone` is None, without consulting any
        injected dependency. Otherwise, returns False if the injected
        enforcement-schedule dependency's `is_active_now(zone.city_code)`
        returns False, without consulting the ticket repository, the
        ambient-label repository, the label-exemption rule, the exemption
        repository, or the zone rule.

        Otherwise, fetches every one of `vehicle_id`'s active ParkingTickets
        at `at` (see module docstring) and applies the zone-aware
        short-circuit: returns False immediately if any of them has
        `(city_code, zone_number) == (None, None)` (legacy, fail-safe) or
        matches `(zone.city_code, zone.zone_number)` (already covered),
        without consulting the ambient-label repository, the label-exemption
        rule, the exemption repository, or the zone rule. If none of the
        vehicle's active tickets satisfies either condition (including when
        there are none), this check does not return and falls through to
        the ambient-label check below exactly as if the vehicle had no
        active tickets at all.

        Otherwise, looks up the vehicle's ambient label. If it resolves to
        `AmbientLabelStatus.FOUND` and the injected `SerLabelExemptionRule`
        dependency's `is_label_exempt(zone.city_code, label)` returns True,
        returns False immediately, without consulting the exemption
        repository or the zone rule (see module docstring). Any other
        ambient-label outcome falls through unchanged to the manual-exemption
        check below.

        Otherwise, looks up the vehicle's stored exemption; if it does
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

        active_tickets = self._ticket_repo.find_all_active_for_vehicle(vehicle_id, at)
        for active_ticket in active_tickets:
            ticket_zone = (active_ticket.city_code, active_ticket.zone_number)
            if ticket_zone == (None, None) or ticket_zone == (zone.city_code, zone.zone_number):
                return False

        ambient_label = self._ambient_label_repo.get_by_vehicle_id(vehicle_id)
        if (
            ambient_label is not None
            and ambient_label.status == AmbientLabelStatus.FOUND
            and ambient_label.label is not None
            and self._label_exemption_rule.is_label_exempt(zone.city_code, ambient_label.label)
        ):
            return False

        exemption = self._exemption_repo.find_by_vehicle_id(vehicle_id)
        if exemption is None or (exemption.city_code, exemption.zone_number) != (
            zone.city_code,
            zone.zone_number,
        ):
            return True
        return not self._exemption_zone_rule.is_zone_eligible(zone)
