"""
Use case: SerZoneRecheckGate.

Shared collaborator, injected into both `SerTicketCreationTriggerHandler` and
`SerTicketNotificationTriggerHandler` (see change-ser-ticket-stationary-recheck
design.md D4), that decides whether a `VehicleLocationUpdated` event is worth
acting on — i.e. whether it should proceed to a
`DetermineSerTicketRequirement` check at all.

Replaces the two handlers' previously near-identical inline previous-
location/distance/zone-comparison blocks (see design.md Context) with one
shared decision (see design.md D3):

- If the vehicle currently holds no active `ParkingTicket` at all
  (`ParkingTicketRepository.find_all_active_for_vehicle` returns an empty
  list), this always signals a recheck, regardless of movement or zone —
  the state that can flip purely with the passage of time (enforcement
  schedule activation, an existing ticket's expiry) is exactly the state a
  stationary vehicle would otherwise never get re-evaluated for.
- If the vehicle does hold at least one active ticket, the movement-floor
  and zone-unchanged skip remain valid pure cost optimizations (see
  design.md D3): `DetermineSerTicketRequirement` would short-circuit to
  `False` for the same zone anyway, so skipping the check when nothing
  relevant changed is safe.

Each caller supplies its own `movement_floor_meters` — the fixed technical
floor for `SerTicketCreationTriggerHandler`, the per-user configurable
threshold for `SerTicketNotificationTriggerHandler` — the two floors remain
independent values, never shared across calls (see design.md D4).
"""

import logging
from dataclasses import dataclass

from mobility_manager.application.use_cases.find_containing_ser_zone import (
    FindContainingSerZone,
)
from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)
from mobility_manager.domain.ports.parking_ticket_repository import (
    ParkingTicketRepository,
)
from mobility_manager.domain.ports.vehicle_location_repository import (
    VehicleLocationRepository,
)
from mobility_manager.domain.value_objects.location import GeoLocation, distance_m

logger = logging.getLogger(__name__)


def _zone_key(zone: SerZone | None) -> tuple[str | None, str | None]:
    """Return `(city_code, zone_number)` for `zone`, or `(None, None)` if `zone` is None."""
    if zone is None:
        return (None, None)
    return (zone.city_code, zone.zone_number)


@dataclass(frozen=True)
class SerZoneRecheckDecision:
    """
    Outcome of `SerZoneRecheckGate.evaluate`.

    `zone` is populated only when `should_check` is `True` — it is the SER
    zone containing the event's coordinates, resolved by the gate so callers
    don't redundantly call `FindContainingSerZone` again.
    """

    should_check: bool
    zone: SerZone | None = None


class SerZoneRecheckGate:
    """Decides whether a VehicleLocationUpdated event warrants a SER zone/requirement check."""

    def __init__(
        self,
        vehicle_location_repo: VehicleLocationRepository,
        find_containing_ser_zone: FindContainingSerZone,
        ticket_repo: ParkingTicketRepository,
    ) -> None:
        self._vehicle_location_repo = vehicle_location_repo
        self._find_containing_ser_zone = find_containing_ser_zone
        self._ticket_repo = ticket_repo

    def evaluate(self, event: VehicleLocationUpdated, movement_floor_meters: float) -> SerZoneRecheckDecision:
        """
        Decide whether `event` warrants a SER zone/requirement recheck.

        First checks whether the vehicle currently holds any active
        `ParkingTicket` at `event.received_at`. If it holds none, always
        returns `should_check=True` with `zone` resolved for the event's
        coordinates, regardless of movement or zone-unchanged.

        If it holds at least one, applies the movement-floor + zone-unchanged
        skip: a vehicle's first-ever recorded location always proceeds (no
        previous location to compare against); otherwise, movement below
        `movement_floor_meters` skips without any zone lookup; otherwise, an
        unchanged SER zone (`(city_code, zone_number)`, `None` as its own
        distinct state) skips; a genuine zone change proceeds with the
        resolved current zone.

        Each of the two skip points logs its own specific reason
        (`logger.info`) — movement-below-floor logs the distance floor used,
        zone-unchanged logs the vehicle id — matching the granularity the
        inline handler code logged before this gate was extracted (post-
        implementation fix: callers no longer need their own generic
        "no recheck needed" log line).
        """
        active_tickets = self._ticket_repo.find_all_active_for_vehicle(event.vehicle_id, at=event.received_at)
        if not active_tickets:
            zone = self._zone_for(event.latitude, event.longitude)
            return SerZoneRecheckDecision(should_check=True, zone=zone)

        previous = self._vehicle_location_repo.get_previous(event.vehicle_id, before=event.received_at)
        if previous is None:
            zone = self._zone_for(event.latitude, event.longitude)
            return SerZoneRecheckDecision(should_check=True, zone=zone)

        distance = distance_m(previous.latitude, previous.longitude, event.latitude, event.longitude)
        if distance < movement_floor_meters:
            logger.info(
                "Movement below GPS-noise floor (%s meters, moved %s meters) for vehicle: %s",
                movement_floor_meters,
                distance,
                event.vehicle_id,
            )
            return SerZoneRecheckDecision(should_check=False, zone=None)

        previous_zone = self._zone_for(previous.latitude, previous.longitude)
        zone = self._zone_for(event.latitude, event.longitude)
        if _zone_key(previous_zone) == _zone_key(zone):
            logger.info("SER zone unchanged for vehicle: %s", event.vehicle_id)
            return SerZoneRecheckDecision(should_check=False, zone=None)
        return SerZoneRecheckDecision(should_check=True, zone=zone)

    def _zone_for(self, lat: float, lng: float) -> SerZone | None:
        """Resolve the SER zone (if any) containing (lat, lng) via FindContainingSerZone."""
        return self._find_containing_ser_zone.execute(GeoLocation(lat=lat, lng=lng))
