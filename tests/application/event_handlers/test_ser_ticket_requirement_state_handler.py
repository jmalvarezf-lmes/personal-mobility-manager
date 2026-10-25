"""
Unit tests for SerTicketRequirementStateHandler.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from mobility_manager.application.event_handlers.ser_ticket_requirement_state_handler import (
    SerTicketRequirementStateHandler,
)
from mobility_manager.domain.entities.vehicle_ser_requirement_state import (
    VehicleSerRequirementState,
)
from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)


class FakeVehicleSerRequirementStateRepository:
    def __init__(self, initial_state: VehicleSerRequirementState | None = None) -> None:
        self.state = initial_state
        self.saved: list[VehicleSerRequirementState] = []
        self.find_calls: list[UUID] = []

    def find_by_vehicle_id(self, vehicle_id: UUID) -> VehicleSerRequirementState | None:
        self.find_calls.append(vehicle_id)
        return self.state

    def save(self, state: VehicleSerRequirementState) -> None:
        self.saved.append(state)
        self.state = state


class FakeEvaluateSerTicketRequirementState:
    def __init__(self, returned_state: VehicleSerRequirementState) -> None:
        self.returned_state = returned_state
        self.calls: list[tuple[VehicleLocationUpdated, VehicleSerRequirementState | None]] = []

    def execute(
        self,
        event: VehicleLocationUpdated,
        current_state: VehicleSerRequirementState | None,
    ) -> VehicleSerRequirementState:
        self.calls.append((event, current_state))
        return self.returned_state


def _make_event(vehicle_id: UUID) -> VehicleLocationUpdated:
    now = datetime.now(UTC)
    return VehicleLocationUpdated(
        vehicle_id=vehicle_id,
        latitude=40.4258,
        longitude=-3.7038,
        recorded_at=now,
        received_at=now,
        source="pull",
    )


def test_loads_state_evaluates_and_saves() -> None:
    vehicle_id = uuid4()
    initial_state = VehicleSerRequirementState(
        vehicle_id=vehicle_id,
        city_code=None,
        zone_number=None,
        is_required=False,
        activated_at=None,
        last_evaluated_at=datetime.now(UTC),
    )
    new_state = VehicleSerRequirementState(
        vehicle_id=vehicle_id,
        city_code="madrid",
        zone_number="163",
        is_required=True,
        activated_at=datetime.now(UTC),
        last_evaluated_at=datetime.now(UTC),
    )
    state_repo = FakeVehicleSerRequirementStateRepository(initial_state)
    evaluate_uc = FakeEvaluateSerTicketRequirementState(new_state)
    handler = SerTicketRequirementStateHandler(
        state_repo=state_repo,  # type: ignore[arg-type]
        evaluate_state=evaluate_uc,  # type: ignore[arg-type]
    )

    event = _make_event(vehicle_id)
    handler.handle(event)

    assert state_repo.find_calls == [vehicle_id]
    assert len(evaluate_uc.calls) == 1
    assert evaluate_uc.calls[0] == (event, initial_state)
    assert state_repo.saved == [new_state]


def test_handles_missing_state_gracefully() -> None:
    vehicle_id = uuid4()
    new_state = VehicleSerRequirementState(
        vehicle_id=vehicle_id,
        city_code=None,
        zone_number=None,
        is_required=False,
        activated_at=None,
        last_evaluated_at=datetime.now(UTC),
    )
    state_repo = FakeVehicleSerRequirementStateRepository(None)
    evaluate_uc = FakeEvaluateSerTicketRequirementState(new_state)
    handler = SerTicketRequirementStateHandler(
        state_repo=state_repo,  # type: ignore[arg-type]
        evaluate_state=evaluate_uc,  # type: ignore[arg-type]
    )

    event = _make_event(vehicle_id)
    handler.handle(event)

    assert evaluate_uc.calls[0] == (event, None)
    assert state_repo.saved == [new_state]


def test_swallows_repository_failure() -> None:
    vehicle_id = uuid4()

    class FailingRepo:
        def find_by_vehicle_id(self, vehicle_id: UUID) -> None:
            raise RuntimeError("db down")

        def save(self, state: VehicleSerRequirementState) -> None:
            pass

    evaluate_uc = FakeEvaluateSerTicketRequirementState(
        VehicleSerRequirementState(
            vehicle_id=vehicle_id,
            city_code=None,
            zone_number=None,
            is_required=False,
            activated_at=None,
            last_evaluated_at=datetime.now(UTC),
        )
    )
    handler = SerTicketRequirementStateHandler(
        state_repo=FailingRepo(),  # type: ignore[arg-type]
        evaluate_state=evaluate_uc,  # type: ignore[arg-type]
    )

    result = handler.handle(_make_event(vehicle_id))

    assert result is None
    assert evaluate_uc.calls == []
