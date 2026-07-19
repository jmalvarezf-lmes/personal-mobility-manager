"""
Application use case: SetVehicleSerParkingExemption.

Sets (or replaces) a vehicle's stored SER parking exemption. Vehicle
ownership is enforced by the caller (see vehicles.py's existing
ownership-check pattern) — this use case only requires a vehicle_id.
"""

from uuid import UUID

from mobility_manager.domain.entities.vehicle_ser_parking_exemption import (
    VehicleSerParkingExemption,
)
from mobility_manager.domain.ports.vehicle_ser_parking_exemption_repository import (
    VehicleSerParkingExemptionRepository,
)


class SetVehicleSerParkingExemption:
    """Upsert a vehicle's SER parking exemption."""

    def __init__(self, exemption_repo: VehicleSerParkingExemptionRepository) -> None:
        self._exemption_repo = exemption_repo

    def execute(self, vehicle_id: UUID, city_code: str, zone_number: str) -> VehicleSerParkingExemption:
        """
        Insert or replace the exemption for `vehicle_id`.

        Raises:
            InvalidSerParkingExemptionZoneError: If (city_code, zone_number)
                has no matching ser_zone_areas row.
        """
        return self._exemption_repo.upsert(vehicle_id, city_code, zone_number)
