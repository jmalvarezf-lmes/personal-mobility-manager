"""
Application use case: ClearVehicleSerParkingExemption.

Clears (deletes) a vehicle's stored SER parking exemption. Vehicle
ownership is enforced by the caller (see vehicles.py's existing
ownership-check pattern) — this use case only requires a vehicle_id.
"""

from uuid import UUID

from mobility_manager.domain.ports.vehicle_ser_parking_exemption_repository import (
    VehicleSerParkingExemptionRepository,
)


class ClearVehicleSerParkingExemption:
    """Delete a vehicle's SER parking exemption, if any (idempotent)."""

    def __init__(self, exemption_repo: VehicleSerParkingExemptionRepository) -> None:
        self._exemption_repo = exemption_repo

    def execute(self, vehicle_id: UUID) -> None:
        """Delete the exemption for `vehicle_id`, if one exists."""
        self._exemption_repo.delete(vehicle_id)
