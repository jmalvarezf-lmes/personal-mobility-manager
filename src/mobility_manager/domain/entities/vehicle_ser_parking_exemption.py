"""
Domain entity: VehicleSerParkingExemption.

Per-vehicle record of a paid SER zone parking exemption. 1:1 with Vehicle,
keyed by vehicle_id — mirrors the existing vehicle_configs/
vehicle_ambient_labels pattern (see design.md D3). Identity is
(city_code, zone_number), matching exactly what SerZone (and thus
FindContainingSerZone's result) carries — see design.md D1.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class VehicleSerParkingExemption:
    """A vehicle's stored SER zone parking exemption."""

    vehicle_id: UUID
    city_code: str
    zone_number: str
    updated_at: datetime
