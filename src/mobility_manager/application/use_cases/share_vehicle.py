"""
Application use case: ShareVehicle.

Grants a registered user read/notification access to a vehicle.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from mobility_manager.domain.entities.vehicle_share import VehicleShare
from mobility_manager.domain.exceptions import (
    UserNotFoundError,
    VehicleNotFoundError,
)
from mobility_manager.domain.ports.user_repository import UserRepository
from mobility_manager.domain.ports.vehicle_repository import VehicleRepository
from mobility_manager.domain.ports.vehicle_share_repository import (
    VehicleShareRepository,
)


@dataclass
class ShareVehicleResult:
    """Outcome of a successful vehicle share."""

    user_id: UUID
    display_name: str
    email: str
    created_at: datetime


class ShareVehicle:
    """Share a vehicle with another registered user by email."""

    def __init__(
        self,
        vehicle_repo: VehicleRepository,
        user_repo: UserRepository,
        share_repo: VehicleShareRepository,
    ) -> None:
        self._vehicle_repo = vehicle_repo
        self._user_repo = user_repo
        self._share_repo = share_repo

    def execute(self, vehicle_id: UUID, owner_id: UUID, sharee_email: str) -> ShareVehicleResult:
        """
        Share the vehicle with the user identified by `sharee_email`.

        Args:
            vehicle_id: UUID of the vehicle to share.
            owner_id: UUID of the authenticated user who must own the vehicle.
            sharee_email: Email of the user to share with.

        Returns:
            ShareVehicleResult with the sharee's id, display name, email and
            the persisted share timestamp.

        Raises:
            VehicleNotFoundError: If the vehicle does not exist or is not owned by owner_id.
            UserNotFoundError: If no user with the given email exists.
            ValueError: If the owner tries to share with themselves.
        """
        vehicle = self._vehicle_repo.get_by_id(vehicle_id)
        if vehicle is None or not vehicle.is_owned_by(owner_id):
            raise VehicleNotFoundError(f"Vehicle {vehicle_id} not found")

        sharee = self._user_repo.find_by_email(sharee_email)
        if sharee is None:
            raise UserNotFoundError(f"No user found with email {sharee_email}")

        if sharee.id == owner_id:
            raise ValueError("Owner cannot share a vehicle with themselves")

        share = VehicleShare(
            vehicle_id=vehicle_id,
            user_id=sharee.id,
            created_at=datetime.now(UTC),
        )
        self._share_repo.save(share)

        return ShareVehicleResult(
            user_id=sharee.id,
            display_name=sharee.display_name,
            email=sharee.email,
            created_at=share.created_at,
        )
