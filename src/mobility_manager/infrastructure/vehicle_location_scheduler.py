"""
Infrastructure: VehicleLocationScheduler.

Mirrors ParkingIngestionScheduler. Polls pull-brand vehicles at a configurable
interval, calling VehiclePullLocationPort.fetch_location for each Toyota vehicle
and delegating to RecordVehicleLocation.

Per-vehicle errors are logged and swallowed so the scheduler continues for
remaining vehicles.
"""

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from mobility_manager.application.use_cases.record_vehicle_location import (
    RecordVehicleLocation,
)
from mobility_manager.domain.ports.vehicle_config_repository import (
    VehicleConfigRepository,
)
from mobility_manager.domain.ports.vehicle_pull_location_port import (
    VehiclePullLocationPort,
)
from mobility_manager.domain.ports.vehicle_repository import VehicleRepository
from mobility_manager.domain.value_objects.brand import Brand

logger = logging.getLogger(__name__)


class VehicleLocationScheduler:
    """
    Schedules periodic location polling for pull-capable vehicles.

    If no pull provider is available (generic-only deployment),
    the scheduler starts but adds no polling jobs.
    """

    def __init__(
        self,
        vehicle_repo: VehicleRepository,
        config_repo: VehicleConfigRepository,
        location_provider: VehiclePullLocationPort | None,
        record_use_case: RecordVehicleLocation,
        interval_minutes: int = 5,
    ) -> None:
        """
        Args:
            vehicle_repo: Used to fetch all Toyota vehicles on each tick.
            config_repo: Used to decrypt per-vehicle Toyota credentials.
            location_provider: Toyota pull provider, or None for push-only deployments.
            record_use_case: Shared use case to persist location rows.
            interval_minutes: How often to poll each vehicle.
        """
        self._vehicle_repo = vehicle_repo
        self._config_repo = config_repo
        self._location_provider = location_provider
        self._record_use_case = record_use_case
        self._interval_minutes = interval_minutes
        self._scheduler = BackgroundScheduler()

    def _run(self) -> None:
        """Poll all Toyota vehicles and record their locations."""
        if self._location_provider is None:
            return

        try:
            vehicles = self._vehicle_repo.get_all_by_brand(Brand.TOYOTA)
        except Exception:
            logger.exception("Failed to fetch Toyota vehicles from repository")
            return

        logger.debug("Polling location for %d Toyota vehicle(s)", len(vehicles))

        for vehicle in vehicles:
            try:
                config = self._config_repo.get_toyota_config(vehicle.id)
                location = self._location_provider.fetch_location(vehicle.id, config)
                if location is None:
                    logger.debug("No location available for vehicle %s this cycle — skipping", vehicle.id)
                    continue
                self._record_use_case.execute(
                    vehicle_id=vehicle.id,
                    lat=location.latitude,
                    lon=location.longitude,
                    recorded_at=location.recorded_at,
                    source="pull",
                )
                logger.info(
                    "Recorded pull location for vehicle %s: lat=%s lon=%s",
                    vehicle.id,
                    location.latitude,
                    location.longitude,
                )
            except Exception:
                logger.exception("Failed to record location for vehicle %s — continuing", vehicle.id)

    def start(self) -> None:
        """Start the scheduler.

        When a provider is configured the first run fires immediately via
        next_run_time so it executes inside APScheduler's own thread pool —
        not in the caller's thread, which may already be running an event loop
        (e.g. FastAPI's lifespan).
        """
        if self._location_provider is not None:
            self._scheduler.add_job(
                self._run,
                "interval",
                minutes=self._interval_minutes,
                id="vehicle_location_poll",
                next_run_time=datetime.now(),
            )

        self._scheduler.start()
        logger.info(
            "Vehicle location scheduler started (interval: %dmin, provider: %s)",
            self._interval_minutes,
            type(self._location_provider).__name__ if self._location_provider else "None",
        )

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        self._scheduler.shutdown(wait=False)
        logger.info("Vehicle location scheduler stopped")
