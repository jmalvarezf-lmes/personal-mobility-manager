"""
Port (interface): VehicleSerRequirementStateRepository.

Abstract contract for persistence of per-vehicle SER ticket requirement state.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from mobility_manager.domain.entities.vehicle_ser_requirement_state import (
    VehicleSerRequirementState,
)


class VehicleSerRequirementStateRepository(ABC):
    """Abstract repository for vehicle SER requirement state."""

    @abstractmethod
    def find_by_vehicle_id(self, vehicle_id: UUID) -> VehicleSerRequirementState | None:
        """Return the current requirement state for the vehicle, or None."""
        ...

    @abstractmethod
    def save(self, state: VehicleSerRequirementState) -> None:
        """Persist the requirement state, inserting or updating as needed."""
        ...
