"""
Application use case: GetVehicleSerParkingExemption.

Reads a vehicle's stored SER parking exemption, if any. Vehicle ownership
is enforced by the caller (the presentation router fetches and checks the
vehicle before invoking this use case — see vehicles.py's existing
ownership-check pattern).
"""

from uuid import UUID

from mobility_manager.domain.entities.vehicle_ser_parking_exemption import (
    VehicleSerParkingExemption,
)
from mobility_manager.domain.ports.vehicle_ser_parking_exemption_repository import (
    VehicleSerParkingExemptionRepository,
)


class GetVehicleSerParkingExemption:
    """Return a vehicle's stored SER parking exemption, or None if unset."""

    def __init__(self, exemption_repo: VehicleSerParkingExemptionRepository) -> None:
        self._exemption_repo = exemption_repo

    def execute(self, vehicle_id: UUID) -> VehicleSerParkingExemption | None:
        """Return the exemption for `vehicle_id`, or None if none is stored."""
        return self._exemption_repo.find_by_vehicle_id(vehicle_id)
