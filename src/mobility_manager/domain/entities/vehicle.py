"""
Domain entity: Vehicle.

Represents a vehicle owned by the user, agnostic of the vendor (Toyota, etc.).
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from mobility_manager.domain.value_objects.brand import Brand


@dataclass
class Vehicle:
    """Core vehicle entity — vendor-agnostic."""

    id: UUID
    brand: Brand
    display_name: str
    vin: str | None
    created_at: datetime
    user_id: UUID
