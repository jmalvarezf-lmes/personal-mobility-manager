"""
Domain entity: VehicleLocation.

Captures a single GPS fix for a vehicle with source tagging (pull or push).
Full history is retained — rows are never overwritten.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID


@dataclass
class VehicleLocation:
    """A single location reading for a vehicle."""

    id: UUID
    vehicle_id: UUID
    latitude: float
    longitude: float
    recorded_at: datetime  # source-device clock
    received_at: datetime  # server clock
    source: Literal["pull", "push"]
