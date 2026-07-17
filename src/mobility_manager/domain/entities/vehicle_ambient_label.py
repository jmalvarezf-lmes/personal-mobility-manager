"""
Domain entity: VehicleAmbientLabel.

Per-vehicle record of DGT ambient label lookup state. 1:1 with Vehicle,
keyed by vehicle_id — mirrors the existing vehicle_configs pattern (see
add-ambient-label-lookup design.md decision 1). Kept separate from the core
Vehicle entity so lookup/polling bookkeeping never touches vehicle identity.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from mobility_manager.domain.value_objects.ambient_label import AmbientLabel
from mobility_manager.domain.value_objects.ambient_label_status import (
    AmbientLabelStatus,
)


@dataclass
class VehicleAmbientLabel:
    """Ambient label lookup state for a single vehicle."""

    vehicle_id: UUID
    label: AmbientLabel | None
    status: AmbientLabelStatus
    last_checked_at: datetime | None
