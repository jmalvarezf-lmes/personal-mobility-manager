"""
Port (interface): VehicleAmbientLabelRepository.

Abstract contract for per-vehicle ambient label lookup state persistence.
1:1 with vehicles, keyed by vehicle_id (see design.md decision 1).
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from uuid import UUID

from mobility_manager.domain.entities.vehicle_ambient_label import (
    VehicleAmbientLabel,
)
from mobility_manager.domain.value_objects.ambient_label import AmbientLabel
from mobility_manager.domain.value_objects.ambient_label_status import (
    AmbientLabelStatus,
)


class VehicleAmbientLabelRepository(ABC):
    """Abstract repository for per-vehicle ambient label lookup state."""

    @abstractmethod
    def get_by_vehicle_id(self, vehicle_id: UUID) -> VehicleAmbientLabel | None:
        """Return the ambient label row for the given vehicle, or None if never looked up."""
        ...

    @abstractmethod
    def upsert(
        self,
        vehicle_id: UUID,
        label: AmbientLabel | None,
        status: AmbientLabelStatus,
        last_checked_at: datetime,
    ) -> None:
        """Insert or update the ambient label row for the given vehicle."""
        ...

    @abstractmethod
    def get_vehicles_needing_lookup(self, cooldown: timedelta) -> list[UUID]:
        """
        Return IDs of vehicles that have a license plate and either no
        ambient label row yet, or a row with status != found whose
        last_checked_at is older than `cooldown`.

        Vehicles whose row has status=found are permanently excluded (see
        design.md decision 2) — this is the sole retry-backlog query used
        by AmbientLabelScheduler.
        """
        ...
