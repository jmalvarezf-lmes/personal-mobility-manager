"""
Port (interface): VehiclePullLocationPort.

Abstract contract for pull-based vehicle location adapters (e.g. Toyota via pytoyoda).
Push-only brands do NOT implement this interface.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from mobility_manager.domain.entities.vehicle_location import VehicleLocation
from mobility_manager.domain.value_objects.toyota_config import ToyotaConfig


class VehiclePullLocationPort(ABC):
    """Abstract pull-location provider — implemented per vendor in infrastructure."""

    @abstractmethod
    def fetch_location(self, vehicle_id: UUID, config: ToyotaConfig) -> VehicleLocation | None:
        """
        Fetch the current GPS location for a vehicle.

        Args:
            vehicle_id: The domain vehicle UUID (used to populate the returned entity).
            config: Decrypted Toyota credentials.

        Returns:
            VehicleLocation with source="pull", or None if the API has no location
            cached for this vehicle right now (transient — try again next cycle).

        Raises:
            VinNotFoundInAccountError: If the VIN is not present in the Toyota account.
            Exception: On network/auth failures.
        """
        ...
