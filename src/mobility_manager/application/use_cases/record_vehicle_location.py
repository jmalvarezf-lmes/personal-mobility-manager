"""
Application use case: RecordVehicleLocation.

Shared entry point for both pull (scheduler) and push (HTTP endpoint) location ingestion.
Validates coordinates and timestamp before persisting.
"""
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID, uuid4

from mobility_manager.domain.entities.vehicle_location import VehicleLocation
from mobility_manager.domain.ports.vehicle_location_repository import (
    VehicleLocationRepository,
)

_MAX_FUTURE_SECONDS = 60


class RecordVehicleLocation:
    """
    Record a GPS location for a vehicle.

    Used by both the pull scheduler and the push HTTP endpoint.
    The caller provides source="pull" or source="push".
    """

    def __init__(self, location_repo: VehicleLocationRepository) -> None:
        self._location_repo = location_repo

    def execute(
        self,
        vehicle_id: UUID,
        lat: float,
        lon: float,
        recorded_at: datetime,
        source: Literal["pull", "push"],
    ) -> None:
        """
        Validate and persist a vehicle location.

        Args:
            vehicle_id: UUID of the vehicle.
            lat: Latitude in WGS84 degrees [-90, 90].
            lon: Longitude in WGS84 degrees [-180, 180].
            recorded_at: When the GPS fix was acquired (source clock).
            source: "pull" (scheduler) or "push" (HTTP endpoint).

        Raises:
            ValueError: If coordinates are out of range or timestamp is too far in the future.
        """
        if not (-90.0 <= lat <= 90.0):
            raise ValueError(f"lat must be in [-90, 90], got {lat}")
        if not (-180.0 <= lon <= 180.0):
            raise ValueError(f"lon must be in [-180, 180], got {lon}")

        # Normalise to UTC
        if recorded_at.tzinfo is None:
            recorded_at_utc = recorded_at.replace(tzinfo=timezone.utc)
        else:
            recorded_at_utc = recorded_at.astimezone(timezone.utc)

        now_utc = datetime.now(timezone.utc)
        if recorded_at_utc > now_utc + timedelta(seconds=_MAX_FUTURE_SECONDS):
            raise ValueError(
                f"recorded_at is more than {_MAX_FUTURE_SECONDS}s in the future"
            )

        location = VehicleLocation(
            id=uuid4(),
            vehicle_id=vehicle_id,
            latitude=lat,
            longitude=lon,
            recorded_at=recorded_at_utc,
            received_at=now_utc,
            source=source,
        )
        self._location_repo.save(location)
