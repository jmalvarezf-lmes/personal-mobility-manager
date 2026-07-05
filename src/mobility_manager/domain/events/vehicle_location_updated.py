"""
Domain event: VehicleLocationUpdated.

Published by RecordVehicleLocation after a vehicle location is successfully
persisted, for both pull (scheduler) and push (HTTP endpoint) sources.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID


@dataclass(frozen=True)
class VehicleLocationUpdated:
    """Raised after a vehicle's location has been recorded."""

    vehicle_id: UUID
    latitude: float
    longitude: float
    recorded_at: datetime
    source: Literal["pull", "push"]
