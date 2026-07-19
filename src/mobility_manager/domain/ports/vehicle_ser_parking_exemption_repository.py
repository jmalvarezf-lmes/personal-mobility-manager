"""
Port (interface): VehicleSerParkingExemptionRepository.

Abstract contract for per-vehicle SER zone parking exemption persistence.
1:1 with vehicles, keyed by vehicle_id (see design.md D3).
"""

from abc import ABC, abstractmethod
from uuid import UUID

from mobility_manager.domain.entities.vehicle_ser_parking_exemption import (
    VehicleSerParkingExemption,
)


class VehicleSerParkingExemptionRepository(ABC):
    """Abstract repository for per-vehicle SER parking exemptions."""

    @abstractmethod
    def find_by_vehicle_id(self, vehicle_id: UUID) -> VehicleSerParkingExemption | None:
        """Return the exemption row for the given vehicle, or None if unset."""
        ...

    @abstractmethod
    def upsert(self, vehicle_id: UUID, city_code: str, zone_number: str) -> VehicleSerParkingExemption:
        """
        Insert or replace the exemption row for the given vehicle.

        Raises:
            InvalidSerParkingExemptionZoneError: If (city_code, zone_number)
                has no matching ser_zone_areas row (composite FK violation).
        """
        ...

    @abstractmethod
    def delete(self, vehicle_id: UUID) -> None:
        """
        Delete the exemption row for the given vehicle, if any.

        Idempotent: deleting a vehicle with no existing exemption row does
        not raise.
        """
        ...
