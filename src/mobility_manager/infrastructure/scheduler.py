"""
Infrastructure: ParkingIngestionScheduler.

Wraps APScheduler BackgroundScheduler to periodically run parking data
ingestion for all registered city providers. One APScheduler job is created
per city so each city ingests independently.
"""

import logging
from collections.abc import Callable
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from mobility_manager.infrastructure.observability.metrics import record_ingestion_run

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class ParkingIngestionScheduler:
    """Schedules periodic parking data ingestion for all registered cities."""

    def __init__(
        self,
        city_use_cases: list[tuple[str, Any]],
        interval_hours: int = 24,
    ) -> None:
        """
        Args:
            city_use_cases: List of (city_code, IngestSerZones) pairs.
            interval_hours: How often to re-ingest each city's data.
        """
        self._city_use_cases = city_use_cases
        self._interval_hours = interval_hours
        self._scheduler = BackgroundScheduler()

    def _make_runner(self, city_code: str, use_case: Any) -> Callable[[], None]:
        def _run() -> None:
            # Root span: this runs in APScheduler's own thread pool, outside
            # any HTTP request context, so there is no ambient trace to
            # attach to (see design.md decision 4).
            with tracer.start_as_current_span("scheduler.parking_ingestion.run") as span:
                span.set_attribute("mobility_manager.city", city_code)
                success = False
                try:
                    summary = use_case.execute()
                    logger.info("Ingestion complete [%s]: %s", city_code, summary)
                    success = True
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR))
                    logger.exception("Ingestion failed [%s]", city_code)
                finally:
                    record_ingestion_run(city=city_code, success=success)

        return _run

    def start(self) -> None:
        """Start the scheduler and trigger an immediate first run per city."""
        for city_code, use_case in self._city_use_cases:
            runner = self._make_runner(city_code, use_case)
            self._scheduler.add_job(
                runner,
                "interval",
                hours=self._interval_hours,
                id=f"parking_ingestion_{city_code}",
            )

        self._scheduler.start()
        logger.info(
            "Parking ingestion scheduler started for %d city/cities (interval: %dh)",
            len(self._city_use_cases),
            self._interval_hours,
        )

        # Trigger immediate first run for every city
        for city_code, use_case in self._city_use_cases:
            self._make_runner(city_code, use_case)()

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        self._scheduler.shutdown(wait=False)
        logger.info("Parking ingestion scheduler stopped")
