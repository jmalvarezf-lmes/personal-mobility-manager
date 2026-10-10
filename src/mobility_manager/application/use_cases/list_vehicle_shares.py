"""
Application use case: ListVehicleShares.

Returns the list of sharees for a vehicle. Owner-only.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from mobility_manager.domain.exceptions import VehicleNotFoundError
from mobility_manager.domain.ports.user_repository import UserRepository
from mobility_manager.domain.ports.vehicle_repository import VehicleRepository
from mobility_manager.domain.ports.vehicle_share_repository import (
    VehicleShareRepository,
)


@dataclass
class VehicleSharee:
    """Sharee information exposed to the owner."""

    user_id: UUID
    display_name: str
    email: str
    created_at: datetime


class ListVehicleShares:
    """List the users a vehicle is shared with."""

    def __init__(
        self,
        vehicle_repo: VehicleRepository,
        share_repo: VehicleShareRepository,
        user_repo: UserRepository,
    ) -> None:
        self._vehicle_repo = vehicle_repo
        self._share_repo = share_repo
        self._user_repo = user_repo

    def execute(self, vehicle_id: UUID, owner_id: UUID) -> list[VehicleSharee]:
        """
        Return sharee details for the vehicle.

        Args:
            vehicle_id: UUID of the vehicle.
            owner_id: UUID of the authenticated user who must own the vehicle.

        Returns:
            List of VehicleSharee objects.

        Raises:
            VehicleNotFoundError: If the vehicle does not exist or is not owned by owner_id.
        """
        vehicle = self._vehicle_repo.get_by_id(vehicle_id)
        if vehicle is None or not vehicle.is_owned_by(owner_id):
            raise VehicleNotFoundError(f"Vehicle {vehicle_id} not found")

        shares = self._share_repo.list_sharees(vehicle_id)
        result: list[VehicleSharee] = []
        for share in shares:
            user = self._user_repo.find_by_id(share.user_id)
            if user is None:
                continue
            result.append(
                VehicleSharee(
                    user_id=user.id,
                    display_name=user.display_name,
                    email=user.email,
                    created_at=share.created_at,
                )
            )
        return result
