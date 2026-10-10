"""
Application use case: RevokeVehicleShare.

Removes a vehicle share grant. Allowed for the vehicle owner or the sharee
removing their own access.
"""

from uuid import UUID

from mobility_manager.domain.exceptions import VehicleNotFoundError
from mobility_manager.domain.ports.vehicle_repository import VehicleRepository
from mobility_manager.domain.ports.vehicle_share_repository import (
    VehicleShareRepository,
)


class RevokeVehicleShare:
    """Revoke a sharee's access to a vehicle."""

    def __init__(
        self,
        vehicle_repo: VehicleRepository,
        share_repo: VehicleShareRepository,
    ) -> None:
        self._vehicle_repo = vehicle_repo
        self._share_repo = share_repo

    def execute(self, vehicle_id: UUID, caller_id: UUID, sharee_user_id: UUID) -> None:
        """
        Delete the share for `sharee_user_id` on `vehicle_id`.

        Args:
            vehicle_id: UUID of the vehicle.
            caller_id: UUID of the user making the request.
            sharee_user_id: UUID of the user whose share is being revoked.

        Raises:
            VehicleNotFoundError: If the vehicle does not exist.
            PermissionError: If the caller is neither the owner nor the sharee.
        """
        vehicle = self._vehicle_repo.get_by_id(vehicle_id)
        if vehicle is None:
            raise VehicleNotFoundError(f"Vehicle {vehicle_id} not found")

        is_owner = vehicle.is_owned_by(caller_id)
        is_self = sharee_user_id == caller_id
        if not (is_owner or is_self):
            raise PermissionError("Only the owner or the sharee can revoke a share")

        self._share_repo.delete(vehicle_id, sharee_user_id)
