"""
Infrastructure: SerZoneIngestionScheduler.

Wraps APScheduler BackgroundScheduler to periodically run SER zone ingestion.
"""
import logging
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)


class SerZoneIngestionScheduler:
    """Schedules periodic SER zone ingestion using APScheduler."""

    def __init__(self, ingest_use_case: Any, interval_hours: int = 24) -> None:
        self._use_case = ingest_use_case
        self._interval_hours = interval_hours
        self._scheduler = BackgroundScheduler()

    def _run(self) -> None:
        try:
            summary = self._use_case.execute()
            logger.info("SER zone ingestion complete: %s", summary)
        except Exception:
            logger.exception("SER zone ingestion failed")

    def start(self) -> None:
        """Start the scheduler and trigger an immediate first run."""
        self._scheduler.add_job(
            self._run,
            "interval",
            hours=self._interval_hours,
            id="ser_zone_ingestion",
        )
        self._scheduler.start()
        logger.info(
            "SER zone ingestion scheduler started (interval: %dh)",
            self._interval_hours,
        )
        # Run immediately on startup
        self._run()

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        self._scheduler.shutdown(wait=False)
        logger.info("SER zone ingestion scheduler stopped")
