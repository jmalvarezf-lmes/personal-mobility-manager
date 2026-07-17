"""
Infrastructure: AmbientLabelScheduler.

Backlog-drain job for DGT ambient label lookups — unlike
VehicleLocationScheduler/ParkingIngestionScheduler, which re-poll their
entire target set every tick, this scheduler only targets vehicles missing
a confident ambient label result (see add-ambient-label-lookup design.md
decision 5). Mirrors VehicleLocationScheduler's per-item try/except + span
pattern. BackgroundScheduler's default max_instances=1 per job id prevents
overlapping runs if a backlog takes longer to drain than the tick interval.
"""

import logging
import time
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from mobility_manager.application.use_cases.lookup_vehicle_ambient_label import (
    LookupVehicleAmbientLabel,
)
from mobility_manager.domain.ports.vehicle_ambient_label_repository import (
    VehicleAmbientLabelRepository,
)
from mobility_manager.domain.ports.vehicle_repository import VehicleRepository

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class AmbientLabelScheduler:
    """Schedules periodic backlog-drain runs for vehicles missing a confident ambient label."""

    def __init__(
        self,
        vehicle_repo: VehicleRepository,
        label_repo: VehicleAmbientLabelRepository,
        lookup_use_case: LookupVehicleAmbientLabel,
        interval_minutes: int = 60,
        retry_cooldown_hours: int = 24,
        request_delay_seconds: int = 5,
    ) -> None:
        """
        Args:
            vehicle_repo: Used to resolve a backlog vehicle_id's current license_plate.
            label_repo: Used to fetch the retry backlog on each tick.
            lookup_use_case: Shared use case to resolve + persist one vehicle's label.
            interval_minutes: How often a tick runs.
            retry_cooldown_hours: Minimum age of a not_found/error row before retry.
            request_delay_seconds: Delay between consecutive DGT requests within a tick.
        """
        self._vehicle_repo = vehicle_repo
        self._label_repo = label_repo
        self._lookup_use_case = lookup_use_case
        self._interval_minutes = interval_minutes
        self._retry_cooldown = timedelta(hours=retry_cooldown_hours)
        self._request_delay_seconds = request_delay_seconds
        self._scheduler = BackgroundScheduler()

    def _run(self) -> None:
        """Drain the backlog of vehicles missing a confident ambient label."""
        try:
            vehicle_ids = self._label_repo.get_vehicles_needing_lookup(self._retry_cooldown)
        except Exception:
            logger.exception("Failed to fetch ambient label backlog")
            return

        logger.debug("Ambient label backlog: %d vehicle(s) need a lookup", len(vehicle_ids))

        for index, vehicle_id in enumerate(vehicle_ids):
            # Root span per vehicle lookup: this runs in APScheduler's own
            # thread pool, outside any HTTP request context, so there is no
            # ambient trace to attach to (see vehicle_location_scheduler.py's
            # equivalent note, referencing add-opentelemetry-observability
            # design.md decision 4).
            with tracer.start_as_current_span("scheduler.ambient_label.lookup") as span:
                try:
                    vehicle = self._vehicle_repo.get_by_id(vehicle_id)
                    if vehicle is None or vehicle.license_plate is None:
                        logger.debug("Vehicle %s no longer has a plate — skipping", vehicle_id)
                    else:
                        self._lookup_use_case.execute(vehicle_id=vehicle_id, license_plate=vehicle.license_plate)
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR))
                    logger.exception("Ambient label lookup failed for vehicle %s — continuing", vehicle_id)

            # Throttle between consecutive lookups, not after the last one in
            # the tick (design.md decision 5).
            if index < len(vehicle_ids) - 1:
                time.sleep(self._request_delay_seconds)

    def start(self) -> None:
        """Start the scheduler.

        The first run fires immediately via next_run_time so it executes
        inside APScheduler's own thread pool — not in the caller's thread,
        which may already be running an event loop (e.g. FastAPI's
        lifespan), mirroring VehicleLocationScheduler.start().
        """
        self._scheduler.add_job(
            self._run,
            "interval",
            minutes=self._interval_minutes,
            id="ambient_label_lookup",
            next_run_time=datetime.now(),
        )
        self._scheduler.start()
        logger.info(
            "Ambient label scheduler started (interval: %dmin, cooldown: %s, delay: %ds)",
            self._interval_minutes,
            self._retry_cooldown,
            self._request_delay_seconds,
        )

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        self._scheduler.shutdown(wait=False)
        logger.info("Ambient label scheduler stopped")
