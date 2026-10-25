"""
Domain entity: VehicleSerRequirementState.

Tracks the computed SER ticket requirement for a single vehicle as durable
state. A vehicle has at most one current requirement at a time, identified
by the zone for which a ticket is required.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class VehicleSerRequirementState:
    """Current SER ticket requirement state for a vehicle."""

    vehicle_id: UUID
    city_code: str | None
    zone_number: str | None
    is_required: bool
    activated_at: datetime | None
    last_evaluated_at: datetime

    def with_last_evaluated(self, last_evaluated_at: datetime) -> VehicleSerRequirementState:
        """Return a copy with an updated `last_evaluated_at`."""
        return VehicleSerRequirementState(
            vehicle_id=self.vehicle_id,
            city_code=self.city_code,
            zone_number=self.zone_number,
            is_required=self.is_required,
            activated_at=self.activated_at,
            last_evaluated_at=last_evaluated_at,
        )
