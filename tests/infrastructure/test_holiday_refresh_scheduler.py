"""
Unit tests for HolidayRefreshScheduler's startup-conditional immediate-fetch
logic (see add-ser-enforcement-calendar design.md D8, tasks.md 8.8).

The real BackgroundScheduler is replaced with an in-process fake that
records add_job()/start()/shutdown() calls, since HolidayRefreshScheduler's
"immediate fetch" fires asynchronously on APScheduler's own thread pool
(via next_run_time) rather than synchronously in the caller's thread —
unlike ParkingIngestionScheduler, there is nothing to observe by just
calling start() and checking a fake use case's `executed` flag; what is
observable and deterministic is whether `next_run_time` is passed to
add_job() at all.
"""

from unittest.mock import MagicMock

import pytest

from mobility_manager.infrastructure import holiday_refresh_scheduler as scheduler_module
from mobility_manager.infrastructure.holiday_refresh_scheduler import (
    HolidayRefreshScheduler,
)


class _FakeAPScheduler:
    """Records add_job/start/shutdown calls instead of actually scheduling anything."""

    def __init__(self) -> None:
        self.add_job_calls: list[dict] = []
        self.started = False
        self.shutdown_called_with: dict | None = None

    def add_job(self, func, trigger, **kwargs):  # noqa: ANN001, ANN201 - matches APScheduler's loose signature
        self.add_job_calls.append({"func": func, "trigger": trigger, **kwargs})

    def start(self) -> None:
        self.started = True

    def shutdown(self, wait: bool = True) -> None:
        self.shutdown_called_with = {"wait": wait}
        self.started = False


class _FakeHolidayRepo:
    def __init__(self, missing_cities: set[str]) -> None:
        self._missing_cities = missing_cities

    def has_no_national_holidays(self, city_code: str) -> bool:
        return city_code in self._missing_cities


@pytest.fixture(autouse=True)
def _patch_background_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler_module, "BackgroundScheduler", _FakeAPScheduler)


def _make_scheduler(
    missing_cities: set[str], city_codes: list[str], interval_hours: int = 4380
) -> HolidayRefreshScheduler:
    refresh_use_case = MagicMock()
    holiday_repo = _FakeHolidayRepo(missing_cities)
    return HolidayRefreshScheduler(
        refresh_use_case=refresh_use_case,
        holiday_repo=holiday_repo,
        city_codes=city_codes,
        interval_hours=interval_hours,
    )


def test_empty_holiday_data_triggers_immediate_fetch_on_startup() -> None:
    """An enabled city with zero ical_national rows -> immediate run (next_run_time set)."""
    scheduler = _make_scheduler(missing_cities={"madrid"}, city_codes=["madrid"])

    scheduler.start()

    fake_scheduler = scheduler._scheduler  # type: ignore[attr-defined]
    assert len(fake_scheduler.add_job_calls) == 1
    assert "next_run_time" in fake_scheduler.add_job_calls[0]
    assert fake_scheduler.started is True


def test_existing_holiday_data_skips_immediate_fetch_on_startup() -> None:
    """Every enabled city already has at least one ical_national row -> no immediate run."""
    scheduler = _make_scheduler(missing_cities=set(), city_codes=["madrid"])

    scheduler.start()

    fake_scheduler = scheduler._scheduler  # type: ignore[attr-defined]
    assert len(fake_scheduler.add_job_calls) == 1
    assert "next_run_time" not in fake_scheduler.add_job_calls[0]


def test_one_city_missing_among_several_still_triggers_immediate_fetch() -> None:
    """
    RefreshPublicHolidays does one shared fetch covering every city, so ANY
    enabled city missing data triggers the single shared immediate run.
    """
    scheduler = _make_scheduler(missing_cities={"barcelona"}, city_codes=["madrid", "barcelona"])

    scheduler.start()

    fake_scheduler = scheduler._scheduler  # type: ignore[attr-defined]
    assert "next_run_time" in fake_scheduler.add_job_calls[0]


def test_configured_interval_hours_is_passed_to_add_job() -> None:
    scheduler = _make_scheduler(missing_cities=set(), city_codes=["madrid"], interval_hours=48)

    scheduler.start()

    fake_scheduler = scheduler._scheduler  # type: ignore[attr-defined]
    assert fake_scheduler.add_job_calls[0]["hours"] == 48
    assert fake_scheduler.add_job_calls[0]["trigger"] == "interval"


def test_stop_shuts_down_the_scheduler_without_waiting() -> None:
    scheduler = _make_scheduler(missing_cities=set(), city_codes=["madrid"])
    scheduler.start()

    scheduler.stop()

    fake_scheduler = scheduler._scheduler  # type: ignore[attr-defined]
    assert fake_scheduler.shutdown_called_with == {"wait": False}


def test_run_never_raises_even_if_refresh_use_case_raises_unexpectedly() -> None:
    """Defense-in-depth: _run() catches everything, even though RefreshPublicHolidays.execute() itself never raises."""
    refresh_use_case = MagicMock()
    refresh_use_case.execute.side_effect = RuntimeError("unexpected bug")
    holiday_repo = _FakeHolidayRepo(missing_cities=set())
    scheduler = HolidayRefreshScheduler(
        refresh_use_case=refresh_use_case,
        holiday_repo=holiday_repo,
        city_codes=["madrid"],
    )

    scheduler._run()  # must not raise

    refresh_use_case.execute.assert_called_once()
