"""
Port (interface): VehicleShareRepository.

Abstract contract for vehicle share persistence.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from mobility_manager.domain.entities.vehicle_share import VehicleShare


class VehicleShareRepository(ABC):
    """Abstract repository for vehicle share grants."""

    @abstractmethod
    def save(self, share: VehicleShare) -> None:
        """Persist a share grant idempotently."""
        ...

    @abstractmethod
    def find_by_vehicle_and_user(self, vehicle_id: UUID, user_id: UUID) -> VehicleShare | None:
        """Return the share for the given vehicle and user, or None."""
        ...

    @abstractmethod
    def list_sharees(self, vehicle_id: UUID) -> list[VehicleShare]:
        """Return all share grants for the given vehicle."""
        ...

    @abstractmethod
    def delete(self, vehicle_id: UUID, user_id: UUID) -> None:
        """Delete the share for the given vehicle and user (idempotent)."""
        ...

    @abstractmethod
    def list_vehicle_ids_for_user(self, user_id: UUID) -> list[UUID]:
        """Return all vehicle ids shared with the given user."""
        ...
