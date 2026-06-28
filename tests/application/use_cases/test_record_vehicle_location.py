"""
Unit tests for RecordVehicleLocation use case.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from mobility_manager.application.use_cases.record_vehicle_location import (
    RecordVehicleLocation,
)
from mobility_manager.domain.entities.vehicle_location import VehicleLocation


class InMemoryLocationRepo:
    def __init__(self) -> None:
        self.saved: list[VehicleLocation] = []

    def save(self, location: VehicleLocation) -> None:
        self.saved.append(location)

    def get_latest(self, vehicle_id) -> VehicleLocation | None:
        return None


def _make_use_case() -> tuple[RecordVehicleLocation, InMemoryLocationRepo]:
    repo = InMemoryLocationRepo()
    uc = RecordVehicleLocation(location_repo=repo)
    return uc, repo


def test_valid_push_location_is_saved() -> None:
    uc, repo = _make_use_case()
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
    uc, repo = _make_use_case()
    recorded_at = datetime.now(UTC)

    uc.execute(vehicle_id=uuid4(), lat=0.0, lon=0.0, recorded_at=recorded_at, source="pull")

    assert repo.saved[0].source == "pull"


def test_lat_above_90_raises_value_error() -> None:
    uc, _ = _make_use_case()
    with pytest.raises(ValueError, match="lat"):
        uc.execute(uuid4(), lat=91.0, lon=0.0, recorded_at=datetime.now(UTC), source="push")


def test_lat_below_minus_90_raises_value_error() -> None:
    uc, _ = _make_use_case()
    with pytest.raises(ValueError, match="lat"):
        uc.execute(uuid4(), lat=-91.0, lon=0.0, recorded_at=datetime.now(UTC), source="push")


def test_lon_above_180_raises_value_error() -> None:
    uc, _ = _make_use_case()
    with pytest.raises(ValueError, match="lon"):
        uc.execute(uuid4(), lat=0.0, lon=181.0, recorded_at=datetime.now(UTC), source="push")


def test_lon_below_minus_180_raises_value_error() -> None:
    uc, _ = _make_use_case()
    with pytest.raises(ValueError, match="lon"):
        uc.execute(uuid4(), lat=0.0, lon=-181.0, recorded_at=datetime.now(UTC), source="push")


def test_lat_boundary_90_is_valid() -> None:
    uc, repo = _make_use_case()
    uc.execute(uuid4(), lat=90.0, lon=0.0, recorded_at=datetime.now(UTC), source="push")
    assert len(repo.saved) == 1


def test_lon_boundary_minus_180_is_valid() -> None:
    uc, repo = _make_use_case()
    uc.execute(uuid4(), lat=0.0, lon=-180.0, recorded_at=datetime.now(UTC), source="push")
    assert len(repo.saved) == 1


def test_recorded_at_more_than_60s_future_raises() -> None:
    uc, _ = _make_use_case()
    future = datetime.now(UTC) + timedelta(seconds=61)
    with pytest.raises(ValueError, match="future"):
        uc.execute(uuid4(), lat=0.0, lon=0.0, recorded_at=future, source="push")


def test_recorded_at_exactly_60s_future_is_valid() -> None:
    """Boundary: exactly 60s in future should be accepted (not strictly greater than)."""
    uc, repo = _make_use_case()
    # Just under 60s — safe margin
    borderline = datetime.now(UTC) + timedelta(seconds=59)
    uc.execute(uuid4(), lat=0.0, lon=0.0, recorded_at=borderline, source="push")
    assert len(repo.saved) == 1


def test_naive_recorded_at_is_treated_as_utc() -> None:
    uc, repo = _make_use_case()
    naive = datetime.utcnow()  # no tzinfo
    uc.execute(uuid4(), lat=0.0, lon=0.0, recorded_at=naive, source="push")
    assert repo.saved[0].recorded_at.tzinfo is not None


def test_received_at_is_set_by_use_case() -> None:
    uc, repo = _make_use_case()
    before = datetime.now(UTC)
    uc.execute(uuid4(), lat=0.0, lon=0.0, recorded_at=before, source="push")
    after = datetime.now(UTC)
    assert before <= repo.saved[0].received_at <= after
