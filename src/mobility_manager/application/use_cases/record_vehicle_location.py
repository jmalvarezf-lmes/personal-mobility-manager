"""
Application use case: RecordVehicleLocation.

Shared entry point for both pull (scheduler) and push (HTTP endpoint) location ingestion.
Validates coordinates and timestamp before persisting.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from mobility_manager.domain.entities.vehicle_location import VehicleLocation
from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)
from mobility_manager.domain.ports.event_publisher import EventPublisher
from mobility_manager.domain.ports.vehicle_location_repository import (
    VehicleLocationRepository,
)

logger = logging.getLogger(__name__)

_MAX_FUTURE_SECONDS = 60


class RecordVehicleLocation:
    """
    Record a GPS location for a vehicle.

    Used by both the pull scheduler and the push HTTP endpoint.
    The caller provides source="pull" or source="push".
    """

    def __init__(self, location_repo: VehicleLocationRepository, event_publisher: EventPublisher) -> None:
        self._location_repo = location_repo
        self._event_publisher = event_publisher

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
        recorded_at_utc = recorded_at.replace(tzinfo=UTC) if recorded_at.tzinfo is None else recorded_at.astimezone(UTC)

        now_utc = datetime.now(UTC)
        if recorded_at_utc > now_utc + timedelta(seconds=_MAX_FUTURE_SECONDS):
            raise ValueError(f"recorded_at is more than {_MAX_FUTURE_SECONDS}s in the future")

        latest = self._location_repo.get_latest(vehicle_id)
        if latest is not None and latest.latitude == lat and latest.longitude == lon:
            logger.info(
                "Discarding duplicate location for vehicle %s (source=%s): unchanged since last stored (%s, %s)",
                vehicle_id,
                source,
                lat,
                lon,
            )
            return

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
        self._event_publisher.publish(
            VehicleLocationUpdated(
                vehicle_id=vehicle_id,
                latitude=lat,
                longitude=lon,
                recorded_at=recorded_at_utc,
                received_at=now_utc,
                source=source,
            )
        )
