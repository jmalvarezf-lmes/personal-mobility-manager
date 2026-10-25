"""
Application event handler: SerTicketRequirementStateHandler.

Subscribed to `VehicleLocationUpdated`. Loads the current
`VehicleSerRequirementState` for the vehicle, delegates transition logic to
`EvaluateSerTicketRequirementState`, and persists the resulting state.

Failures are contained here and never propagate to the event publisher, so
a problem in this handler does not block sibling handlers such as
`SerTicketCreationTriggerHandler`.
"""

import logging

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from mobility_manager.application.use_cases.evaluate_ser_ticket_requirement_state import (
    EvaluateSerTicketRequirementState,
)
from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)
from mobility_manager.domain.ports.vehicle_ser_requirement_state_repository import (
    VehicleSerRequirementStateRepository,
)

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class SerTicketRequirementStateHandler:
    """Maintains vehicle SER requirement state in response to location updates."""

    def __init__(
        self,
        state_repo: VehicleSerRequirementStateRepository,
        evaluate_state: EvaluateSerTicketRequirementState,
    ) -> None:
        self._state_repo = state_repo
        self._evaluate_state = evaluate_state

    def handle(self, event: VehicleLocationUpdated) -> None:
        """
        Load state, evaluate the current requirement, and persist the result.

        The entire body is wrapped in a broad try/except so that a failure in
        any collaborator is contained here and never propagates to the caller.
        The whole call is also wrapped in a root trace span.
        """
        with tracer.start_as_current_span("event_handler.ser_ticket_requirement_state") as span:
            try:
                current_state = self._state_repo.find_by_vehicle_id(event.vehicle_id)
                new_state = self._evaluate_state.execute(event, current_state)
                self._state_repo.save(new_state)
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                logger.exception("Failed to evaluate SER requirement state for vehicle: %s", event.vehicle_id)
