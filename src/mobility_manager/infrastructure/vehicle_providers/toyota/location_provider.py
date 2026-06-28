"""
Infrastructure adapter: ToyotaLocationProvider.

Implements VehiclePullLocationPort using the pytoyoda library.
Authenticates with the Toyota MyT API, locates the vehicle by VIN,
and returns a VehicleLocation with source="pull".

Note: pytoyoda uses async internally. This adapter wraps the async calls with
asyncio.run() so it can be used from the synchronous APScheduler BackgroundScheduler.
"""
import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from pytoyoda import MyT  # type: ignore[attr-defined]

from mobility_manager.domain.entities.vehicle_location import VehicleLocation
from mobility_manager.domain.exceptions import VinNotFoundInAccountError
from mobility_manager.domain.ports.vehicle_pull_location_port import (
    VehiclePullLocationPort,
)
from mobility_manager.domain.value_objects.toyota_config import ToyotaConfig

logger = logging.getLogger(__name__)


class ToyotaLocationProvider(VehiclePullLocationPort):
    """Fetches vehicle location from the Toyota MyT API via pytoyoda."""

    def fetch_location(self, vehicle_id: UUID, config: ToyotaConfig) -> VehicleLocation:
        """
        Authenticate with Toyota and return the current GPS location.

        Args:
            vehicle_id: Domain vehicle UUID (used to tag the returned entity).
            config: Decrypted Toyota credentials.

        Returns:
            VehicleLocation with source="pull".

        Raises:
            VinNotFoundInAccountError: If the VIN is not in the Toyota account
                or location data is unavailable.
        """
        return asyncio.run(self._fetch_async(vehicle_id, config))

    async def _fetch_async(
        self, vehicle_id: UUID, config: ToyotaConfig
    ) -> VehicleLocation:
        client = MyT(username=config.username, password=config.password)
        vehicles = await client.get_vehicles()

        target = None
        for v in vehicles:
            if v is not None and v.vin == config.vin:
                target = v
                break

        if target is None:
            raise VinNotFoundInAccountError(
                f"VIN {config.vin!r} not found in Toyota account for user {config.username!r}"
            )

        # Fetch only the location endpoint to avoid rate-limiting bursts
        await target.update(only=["location"])

        location = target.location
        if location is None or location.latitude is None or location.longitude is None:
            raise VinNotFoundInAccountError(
                f"No location data available for VIN {config.vin!r}"
            )

        recorded_at = location.timestamp
        now_utc = datetime.now(timezone.utc)
        if recorded_at is None:
            recorded_at = now_utc
        elif recorded_at.tzinfo is None:
            recorded_at = recorded_at.replace(tzinfo=timezone.utc)

        logger.debug(
            "Fetched location for VIN %s: lat=%s lon=%s recorded_at=%s",
            config.vin,
            location.latitude,
            location.longitude,
            recorded_at,
        )

        return VehicleLocation(
            id=uuid4(),
            vehicle_id=vehicle_id,
            latitude=location.latitude,
            longitude=location.longitude,
            recorded_at=recorded_at,
            received_at=now_utc,
            source="pull",
        )
