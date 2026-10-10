"""
Domain entity: VehicleShare.

Represents a grant that allows a user (sharee) to view a vehicle and
receive its notifications without owning it.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class VehicleShare:
    """Grant of read/notification access to a vehicle for a non-owner user."""

    vehicle_id: UUID
    user_id: UUID
    created_at: datetime
