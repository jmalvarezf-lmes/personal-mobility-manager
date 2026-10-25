"""
Application use case: EvaluateSerTicketRequirementState.

Computes whether a SER ticket is currently required for a vehicle, compares
that against the stored requirement state, and emits domain events on
transitions. The caller is responsible for loading the current state before
calling this use case and persisting the returned state afterwards.
"""

from datetime import UTC, datetime

from mobility_manager.application.use_cases.determine_ser_ticket_requirement import (
    DetermineSerTicketRequirement,
)
from mobility_manager.application.use_cases.find_containing_ser_zone import (
    FindContainingSerZone,
)
from mobility_manager.application.use_cases.ser_zone_recheck_gate import (
    SerZoneRecheckGate,
)
from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.entities.vehicle_ser_requirement_state import (
    VehicleSerRequirementState,
)
from mobility_manager.domain.events.ser_ticket_requirement_activated import (
    SerTicketRequirementActivated,
)
from mobility_manager.domain.events.ser_ticket_requirement_deactivated import (
    SerTicketRequirementDeactivated,
)
from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)
from mobility_manager.domain.ports.event_publisher import EventPublisher
from mobility_manager.domain.ports.parking_ticket_repository import (
    ParkingTicketRepository,
)
from mobility_manager.domain.value_objects.location import GeoLocation
from mobility_manager.domain.value_objects.ser_ticket_requirement_deactivation_reason import (
    SerTicketRequirementDeactivationReason,
)


class EvaluateSerTicketRequirementState:
    """
    Evaluate the current SER ticket requirement for a vehicle and emit
    transition events when the requirement state changes.
    """

    def __init__(
        self,
        ser_zone_recheck_gate: SerZoneRecheckGate,
        find_containing_ser_zone: FindContainingSerZone,
        determine_ser_ticket_requirement: DetermineSerTicketRequirement,
        ticket_repo: ParkingTicketRepository,
        event_publisher: EventPublisher,
        movement_floor_meters: float = 0.0,
    ) -> None:
        """
        Args:
            ser_zone_recheck_gate: Gate used when state is inactive to avoid
                unnecessary zone lookups.
            find_containing_ser_zone: Resolves the SER zone containing a point.
            determine_ser_ticket_requirement: Decides whether a ticket is
                required for a given zone and vehicle at a given time.
            ticket_repo: Used to determine deactivation reason when a ticket
                becomes active for the current zone.
            event_publisher: Publishes activation/deactivation events.
            movement_floor_meters: GPS-noise floor passed to the gate when the
                stored state is inactive. Defaults to 0 (always recheck).
        """
        self._ser_zone_recheck_gate = ser_zone_recheck_gate
        self._find_containing_ser_zone = find_containing_ser_zone
        self._determine_ser_ticket_requirement = determine_ser_ticket_requirement
        self._ticket_repo = ticket_repo
        self._event_publisher = event_publisher
        self._movement_floor_meters = movement_floor_meters

    def execute(
        self,
        event: VehicleLocationUpdated,
        current_state: VehicleSerRequirementState | None,
    ) -> VehicleSerRequirementState:
        """
        Compute the current requirement and transition the stored state.

        Returns the updated state. The caller must persist it.
        """
        state = current_state or self._default_state(event.vehicle_id)

        if state.is_required:
            # When already active, always re-evaluate so we detect
            # deactivation reliably (ticket created, enforcement ended, etc.).
            decision_zone = self._find_containing_ser_zone.execute(
                GeoLocation(lat=event.latitude, lng=event.longitude)
            )
            required = self._determine_ser_ticket_requirement.execute(
                decision_zone, event.vehicle_id, at=event.received_at
            )
            return self._transition(event, state, decision_zone, required)

        # Inactive: use the gate to avoid unnecessary work.
        decision = self._ser_zone_recheck_gate.evaluate(
            event, movement_floor_meters=self._movement_floor_meters
        )
        if not decision.should_check:
            return state.with_last_evaluated(event.received_at)

        required = self._determine_ser_ticket_requirement.execute(
            decision.zone, event.vehicle_id, at=event.received_at
        )
        return self._transition(event, state, decision.zone, required)

    def _default_state(self, vehicle_id: object) -> VehicleSerRequirementState:
        """Return a fresh inactive state for a vehicle with no stored state."""
        return VehicleSerRequirementState(
            vehicle_id=vehicle_id,  # type: ignore[arg-type]
            city_code=None,
            zone_number=None,
            is_required=False,
            activated_at=None,
            last_evaluated_at=datetime.now(UTC),
        )

    def _transition(
        self,
        event: VehicleLocationUpdated,
        state: VehicleSerRequirementState,
        zone: SerZone | None,
        required: bool,
    ) -> VehicleSerRequirementState:
        """Compare computed requirement with stored state and publish events."""
        city_code = zone.city_code if zone is not None else None
        zone_number = zone.zone_number if zone is not None else None

        if required and not state.is_required:
            new_state = VehicleSerRequirementState(
                vehicle_id=state.vehicle_id,
                city_code=city_code,
                zone_number=zone_number,
                is_required=True,
                activated_at=event.received_at,
                last_evaluated_at=event.received_at,
            )
            self._event_publisher.publish(
                SerTicketRequirementActivated(
                    vehicle_id=state.vehicle_id,
                    city_code=city_code,
                    zone_number=zone_number,
                    latitude=event.latitude,
                    longitude=event.longitude,
                    activated_at=event.received_at,
                )
            )
            return new_state

        if not required and state.is_required:
            reason = self._deactivation_reason(zone, state, event)
            new_state = VehicleSerRequirementState(
                vehicle_id=state.vehicle_id,
                city_code=city_code,
                zone_number=zone_number,
                is_required=False,
                activated_at=None,
                last_evaluated_at=event.received_at,
            )
            self._event_publisher.publish(
                SerTicketRequirementDeactivated(
                    vehicle_id=state.vehicle_id,
                    city_code=state.city_code,
                    zone_number=state.zone_number,
                    deactivated_at=event.received_at,
                    reason=reason,
                )
            )
            return new_state

        return state.with_last_evaluated(event.received_at)

    def _deactivation_reason(
        self,
        zone: SerZone | None,
        state: VehicleSerRequirementState,
        event: VehicleLocationUpdated,
    ) -> SerTicketRequirementDeactivationReason:
        """Determine why the requirement deactivated."""
        if zone is None:
            return SerTicketRequirementDeactivationReason.LEFT_ZONE

        active_tickets = self._ticket_repo.find_all_active_for_vehicle(
            state.vehicle_id, at=event.received_at
        )
        for ticket in active_tickets:
            ticket_zone = (ticket.city_code, ticket.zone_number)
            if ticket_zone == (None, None) or ticket_zone == (zone.city_code, zone.zone_number):
                return SerTicketRequirementDeactivationReason.TICKET_ACTIVE

        # No active ticket for the zone and still inside a zone: treat as
        # enforcement inactive as the catch-all (covers schedule and exemptions).
        return SerTicketRequirementDeactivationReason.ENFORCEMENT_INACTIVE
