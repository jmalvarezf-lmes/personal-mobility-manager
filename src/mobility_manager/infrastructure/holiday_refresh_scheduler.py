"""
Infrastructure: HolidayRefreshScheduler.

Wraps APScheduler BackgroundScheduler to periodically refresh public
holidays for all enabled cities via RefreshPublicHolidays — see
add-ser-enforcement-calendar design.md D7/D8.

Startup-conditional immediate fetch, and how it reconciles with
RefreshPublicHolidays' single-shared-fetch design:

RefreshPublicHolidays.execute() fetches the national holiday feed exactly
ONCE per run and then upserts the same fetched records into EVERY given
city's `holidays` rows (design.md D7) — there is no per-city fetch to
isolate. Design.md D8's scheduler contract is phrased per-city ("fire
immediately for a city with zero source='ical_national' rows"), which
would suggest per-city triggering — but since one shared fetch already
serves every city in a single call, running that shared fetch once at
startup covers every city that needs it at no extra cost. The reconciled
rule this class implements: if ANY enabled city currently has zero
`ical_national` rows, fire the single shared refresh job immediately at
startup (via `next_run_time`, mirroring AmbientLabelScheduler's pattern);
if every enabled city already has at least one row, skip the immediate
fire and let the normal interval apply to all of them together.
"""

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from mobility_manager.application.use_cases.refresh_public_holidays import (
    RefreshPublicHolidays,
)
from mobility_manager.domain.ports.holiday_repository import HolidayRepository
from mobility_manager.infrastructure.observability.metrics import record_holiday_refresh_run

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class HolidayRefreshScheduler:
    """Schedules periodic public holiday refresh runs for all enabled cities."""

    def __init__(
        self,
        refresh_use_case: RefreshPublicHolidays,
        holiday_repo: HolidayRepository,
        city_codes: list[str],
        interval_hours: int = 4380,
    ) -> None:
        """
        Args:
            refresh_use_case: Shared use case — fetches once, upserts into
                every city in `city_codes` (see module docstring).
            holiday_repo: Used to check each city's `has_no_national_holidays()`
                at startup, to decide whether to fire immediately.
            city_codes: Enabled city codes to check at startup — should be
                the same set the refresh_use_case was constructed with.
            interval_hours: How often the refresh re-runs (default: 4380h / 6 months).
        """
        self._refresh_use_case = refresh_use_case
        self._holiday_repo = holiday_repo
        self._city_codes = city_codes
        self._interval_hours = interval_hours
        self._scheduler = BackgroundScheduler()

    def _run(self) -> None:
        """Run the shared holiday refresh. Never raises (defense in depth)."""
        # Root span: this runs in APScheduler's own thread pool, outside any
        # HTTP request context, so there is no ambient trace to attach to
        # (see ParkingIngestionScheduler._make_runner()'s equivalent note).
        with tracer.start_as_current_span("scheduler.holiday_refresh.run") as span:
            success = False
            try:
                self._refresh_use_case.execute()
                success = True
            except Exception as exc:
                # RefreshPublicHolidays.execute() already catches and logs
                # provider errors without raising (see its own docstring) — this
                # is a second layer of isolation so a genuinely unexpected bug
                # here still can't crash the scheduler or app startup, matching
                # AmbientLabelScheduler's per-tick isolation convention.
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                logger.exception("Holiday refresh run failed unexpectedly")
            finally:
                record_holiday_refresh_run(success=success)

    def start(self) -> None:
        """
        Start the scheduler.

        Fires an immediate first run only if at least one enabled city
        currently has zero `source='ical_national'` holiday rows (see
        module docstring for the shared-fetch reconciliation). Otherwise
        the first run waits for the configured interval, unlike
        AmbientLabelScheduler/ParkingIngestionScheduler which always fire
        unconditionally on startup.
        """
        any_city_missing_holidays = any(
            self._holiday_repo.has_no_national_holidays(city_code) for city_code in self._city_codes
        )

        job_kwargs: dict[str, object] = {}
        if any_city_missing_holidays:
            job_kwargs["next_run_time"] = datetime.now()

        self._scheduler.add_job(
            self._run,
            "interval",
            hours=self._interval_hours,
            id="holiday_refresh",
            **job_kwargs,
        )
        self._scheduler.start()
        logger.info(
            "Holiday refresh scheduler started (interval: %dh, immediate fetch: %s)",
            self._interval_hours,
            any_city_missing_holidays,
        )

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        self._scheduler.shutdown(wait=False)
        logger.info("Holiday refresh scheduler stopped")
