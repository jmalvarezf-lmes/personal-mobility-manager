"""
Application use case: DeleteVehicle.

Deletes a vehicle after verifying it exists.
Cascade FK constraints in the DB remove child rows automatically (D4).
"""

from uuid import UUID

from mobility_manager.domain.exceptions import VehicleNotFoundError
from mobility_manager.domain.ports.vehicle_repository import VehicleRepository


class DeleteVehicle:
    """Delete a vehicle by ID; cascading DB constraints clean up related rows."""

    def __init__(self, vehicle_repo: VehicleRepository) -> None:
        self._vehicle_repo = vehicle_repo

    def execute(self, vehicle_id: UUID) -> None:
        """
        Delete the vehicle.

        Args:
            vehicle_id: UUID of the vehicle to delete.

        Raises:
            VehicleNotFoundError: If no vehicle exists with the given ID.
        """
        vehicle = self._vehicle_repo.get_by_id(vehicle_id)
        if vehicle is None:
            raise VehicleNotFoundError(f"Vehicle {vehicle_id} not found")
        self._vehicle_repo.delete(vehicle_id)
