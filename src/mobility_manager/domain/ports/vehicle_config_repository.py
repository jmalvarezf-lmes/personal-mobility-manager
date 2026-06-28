"""
Port (interface): VehicleConfigRepository.

Abstract contract for per-vehicle configuration storage.
Toyota credentials are stored AES-encrypted; generic token is cleartext.
"""
from abc import ABC, abstractmethod
from uuid import UUID

from mobility_manager.domain.value_objects.generic_config import GenericConfig
from mobility_manager.domain.value_objects.toyota_config import ToyotaConfig


class VehicleConfigRepository(ABC):
    """Abstract repository for vehicle configuration (credentials and tokens)."""

    @abstractmethod
    def save_toyota_config(self, vehicle_id: UUID, config: ToyotaConfig) -> None:
        """Persist Toyota credentials (will be AES-encrypted by the implementation)."""
        ...

    @abstractmethod
    def save_generic_config(self, vehicle_id: UUID, config: GenericConfig) -> None:
        """Persist generic vehicle config (location_token stored cleartext)."""
        ...

    @abstractmethod
    def get_toyota_config(self, vehicle_id: UUID) -> ToyotaConfig:
        """
        Return the decrypted Toyota config for the given vehicle.

        Raises:
            VehicleConfigNotFoundError: If no Toyota config exists.
        """
        ...

    @abstractmethod
    def get_generic_config(self, vehicle_id: UUID) -> GenericConfig | None:
        """Return the generic config for the given vehicle, or None if not found."""
        ...

    @abstractmethod
    def find_vehicle_by_token(self, token: str) -> UUID | None:
        """
        Resolve a push-endpoint token to a vehicle UUID.

        Returns None if no vehicle config has the given location_token.
        """
        ...
