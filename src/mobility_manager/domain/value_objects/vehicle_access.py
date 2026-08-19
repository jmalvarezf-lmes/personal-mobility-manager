"""
Domain value object: VehicleAccess.

Bundles a vehicle with the authenticated user's relationship to it.
"""

from dataclasses import dataclass

from mobility_manager.domain.entities.vehicle import Vehicle


@dataclass(frozen=True)
class VehicleAccess:
    """Vehicle plus a flag indicating whether the caller is its owner."""

    vehicle: Vehicle
    is_owner: bool
