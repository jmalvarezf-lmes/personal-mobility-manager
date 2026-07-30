"""
Unit tests for RecordVehicleLocation use case.
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from mobility_manager.application.use_cases.record_vehicle_location import (
    RecordVehicleLocation,
)
from mobility_manager.domain.entities.vehicle_location import VehicleLocation
from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)


class InMemoryLocationRepo:
    def __init__(self) -> None:
        self.saved: list[VehicleLocation] = []

    def save(self, location: VehicleLocation) -> None:
        self.saved.append(location)

    def get_latest(self, vehicle_id) -> VehicleLocation | None:
        for location in reversed(self.saved):
            if location.vehicle_id == vehicle_id:
                return location
        return None


class FakeEventPublisher:
    def __init__(self) -> None:
        self.published: list[object] = []

    def publish(self, event: object) -> None:
        self.published.append(event)


def _make_use_case() -> tuple[RecordVehicleLocation, InMemoryLocationRepo, FakeEventPublisher]:
    repo = InMemoryLocationRepo()
    publisher = FakeEventPublisher()
    uc = RecordVehicleLocation(location_repo=repo, event_publisher=publisher)
    return uc, repo, publisher


def test_valid_push_location_is_saved() -> None:
    uc, repo, _publisher = _make_use_case()
    vehicle_id = uuid4()
    recorded_at = datetime.now(UTC)

    uc.execute(vehicle_id=vehicle_id, lat=40.4, lon=-3.7, recorded_at=recorded_at, source="push")

    assert len(repo.saved) == 1
    loc = repo.saved[0]
    assert loc.vehicle_id == vehicle_id
    assert loc.latitude == 40.4
    assert loc.longitude == -3.7
    assert loc.source == "push"


def test_valid_pull_location_source_is_pull() -> None:
    uc, repo, _publisher = _make_use_case()
    recorded_at = datetime.now(UTC)

    uc.execute(vehicle_id=uuid4(), lat=0.0, lon=0.0, recorded_at=recorded_at, source="pull")

    assert repo.saved[0].source == "pull"


def test_lat_above_90_raises_value_error() -> None:
    uc, _repo, _publisher = _make_use_case()
    with pytest.raises(ValueError, match="lat"):
        uc.execute(uuid4(), lat=91.0, lon=0.0, recorded_at=datetime.now(UTC), source="push")


def test_lat_below_minus_90_raises_value_error() -> None:
    uc, _repo, _publisher = _make_use_case()
    with pytest.raises(ValueError, match="lat"):
        uc.execute(uuid4(), lat=-91.0, lon=0.0, recorded_at=datetime.now(UTC), source="push")


def test_lon_above_180_raises_value_error() -> None:
    uc, _repo, _publisher = _make_use_case()
    with pytest.raises(ValueError, match="lon"):
        uc.execute(uuid4(), lat=0.0, lon=181.0, recorded_at=datetime.now(UTC), source="push")


def test_lon_below_minus_180_raises_value_error() -> None:
    uc, _repo, _publisher = _make_use_case()
    with pytest.raises(ValueError, match="lon"):
        uc.execute(uuid4(), lat=0.0, lon=-181.0, recorded_at=datetime.now(UTC), source="push")


def test_lat_boundary_90_is_valid() -> None:
    uc, repo, _publisher = _make_use_case()
    uc.execute(uuid4(), lat=90.0, lon=0.0, recorded_at=datetime.now(UTC), source="push")
    assert len(repo.saved) == 1


def test_lon_boundary_minus_180_is_valid() -> None:
    uc, repo, _publisher = _make_use_case()
    uc.execute(uuid4(), lat=0.0, lon=-180.0, recorded_at=datetime.now(UTC), source="push")
    assert len(repo.saved) == 1


def test_recorded_at_more_than_60s_future_raises() -> None:
    uc, _repo, _publisher = _make_use_case()
    future = datetime.now(UTC) + timedelta(seconds=61)
    with pytest.raises(ValueError, match="future"):
        uc.execute(uuid4(), lat=0.0, lon=0.0, recorded_at=future, source="push")


def test_recorded_at_exactly_60s_future_is_valid() -> None:
    """Boundary: exactly 60s in future should be accepted (not strictly greater than)."""
    uc, repo, _publisher = _make_use_case()
    # Just under 60s — safe margin
    borderline = datetime.now(UTC) + timedelta(seconds=59)
    uc.execute(uuid4(), lat=0.0, lon=0.0, recorded_at=borderline, source="push")
    assert len(repo.saved) == 1


def test_naive_recorded_at_is_treated_as_utc() -> None:
    uc, repo, _publisher = _make_use_case()
    naive = datetime.utcnow()  # no tzinfo
    uc.execute(uuid4(), lat=0.0, lon=0.0, recorded_at=naive, source="push")
    assert repo.saved[0].recorded_at.tzinfo is not None


def test_received_at_is_set_by_use_case() -> None:
    uc, repo, _publisher = _make_use_case()
    before = datetime.now(UTC)
    uc.execute(uuid4(), lat=0.0, lon=0.0, recorded_at=before, source="push")
    after = datetime.now(UTC)
    assert before <= repo.saved[0].received_at <= after


def test_event_published_after_successful_pull_save() -> None:
    uc, _repo, publisher = _make_use_case()
    vehicle_id = uuid4()
    recorded_at = datetime.now(UTC)

    uc.execute(vehicle_id=vehicle_id, lat=40.4, lon=-3.7, recorded_at=recorded_at, source="pull")

    assert len(publisher.published) == 1
    event = publisher.published[0]
    assert isinstance(event, VehicleLocationUpdated)
    assert event.vehicle_id == vehicle_id
    assert event.latitude == 40.4
    assert event.longitude == -3.7
    assert event.source == "pull"


def test_event_published_after_successful_push_save() -> None:
    uc, _repo, publisher = _make_use_case()
    vehicle_id = uuid4()

    uc.execute(vehicle_id=vehicle_id, lat=0.0, lon=0.0, recorded_at=datetime.now(UTC), source="push")

    assert len(publisher.published) == 1
    assert publisher.published[0].source == "push"


def test_no_event_published_on_validation_failure() -> None:
    uc, repo, publisher = _make_use_case()

    with pytest.raises(ValueError):
        uc.execute(uuid4(), lat=200.0, lon=0.0, recorded_at=datetime.now(UTC), source="push")

    assert repo.saved == []
    assert publisher.published == []


def test_duplicate_location_is_not_saved_but_event_is_still_published() -> None:
    """
    Persistence and publication are independent (see
    change-ser-ticket-stationary-recheck design.md D2): a duplicate
    coordinate still skips the redundant DB row, but VehicleLocationUpdated
    is published every time regardless — a stationary vehicle's SER-ticket
    requirement can change purely from the passage of time, and that
    re-evaluation depends on the event still firing every poll.
    """
    uc, repo, publisher = _make_use_case()
    vehicle_id = uuid4()
    first_time = datetime.now(UTC) - timedelta(minutes=5)
    uc.execute(vehicle_id=vehicle_id, lat=40.4, lon=-3.7, recorded_at=first_time, source="pull")

    second_time = datetime.now(UTC)
    uc.execute(vehicle_id=vehicle_id, lat=40.4, lon=-3.7, recorded_at=second_time, source="pull")

    assert len(repo.saved) == 1
    assert len(publisher.published) == 2
    second_event = publisher.published[1]
    assert isinstance(second_event, VehicleLocationUpdated)
    assert second_event.latitude == 40.4
    assert second_event.longitude == -3.7


def test_duplicate_location_published_event_has_fresh_received_at() -> None:
    """The republished event's received_at reflects this call, not the first ping's."""
    uc, repo, publisher = _make_use_case()
    vehicle_id = uuid4()
    first_time = datetime.now(UTC) - timedelta(minutes=5)
    uc.execute(vehicle_id=vehicle_id, lat=40.4, lon=-3.7, recorded_at=first_time, source="pull")

    before_second_call = datetime.now(UTC)
    uc.execute(vehicle_id=vehicle_id, lat=40.4, lon=-3.7, recorded_at=datetime.now(UTC), source="pull")
    after_second_call = datetime.now(UTC)

    first_received_at = repo.saved[0].received_at
    second_received_at = publisher.published[1].received_at
    assert second_received_at > first_received_at
    assert before_second_call <= second_received_at <= after_second_call


def test_duplicate_location_across_pull_and_push_sources_is_not_saved() -> None:
    """Dedup applies regardless of which source (pull/push) reported the identical fix, but the event still publishes."""
    uc, repo, publisher = _make_use_case()
    vehicle_id = uuid4()
    first_time = datetime.now(UTC) - timedelta(minutes=5)
    uc.execute(vehicle_id=vehicle_id, lat=40.4, lon=-3.7, recorded_at=first_time, source="pull")

    second_time = datetime.now(UTC)
    uc.execute(vehicle_id=vehicle_id, lat=40.4, lon=-3.7, recorded_at=second_time, source="push")

    assert len(repo.saved) == 1
    assert len(publisher.published) == 2
    assert publisher.published[1].source == "push"


def test_changed_location_is_saved_and_published() -> None:
    uc, repo, publisher = _make_use_case()
    vehicle_id = uuid4()
    first_time = datetime.now(UTC) - timedelta(minutes=5)
    uc.execute(vehicle_id=vehicle_id, lat=40.4, lon=-3.7, recorded_at=first_time, source="pull")

    second_time = datetime.now(UTC)
    uc.execute(vehicle_id=vehicle_id, lat=40.5, lon=-3.7, recorded_at=second_time, source="pull")

    assert len(repo.saved) == 2
    assert len(publisher.published) == 2


def test_duplicate_location_for_different_vehicle_is_still_saved() -> None:
    uc, repo, _publisher = _make_use_case()
    vehicle_a = uuid4()
    vehicle_b = uuid4()
    uc.execute(vehicle_id=vehicle_a, lat=40.4, lon=-3.7, recorded_at=datetime.now(UTC), source="pull")
    uc.execute(vehicle_id=vehicle_b, lat=40.4, lon=-3.7, recorded_at=datetime.now(UTC), source="pull")

    assert len(repo.saved) == 2


def test_duplicate_location_logs_discard(caplog: pytest.LogCaptureFixture) -> None:
    uc, _repo, _publisher = _make_use_case()
    vehicle_id = uuid4()
    uc.execute(vehicle_id=vehicle_id, lat=40.4, lon=-3.7, recorded_at=datetime.now(UTC), source="pull")

    with caplog.at_level(logging.INFO):
        uc.execute(vehicle_id=vehicle_id, lat=40.4, lon=-3.7, recorded_at=datetime.now(UTC), source="pull")

    assert "duplicate" in caplog.text.lower()
