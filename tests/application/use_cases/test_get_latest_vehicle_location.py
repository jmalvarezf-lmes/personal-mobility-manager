"""
Unit tests for GetLatestVehicleLocation use case.
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from mobility_manager.application.use_cases.get_latest_vehicle_location import (
    GetLatestVehicleLocation,
)
from mobility_manager.domain.entities.vehicle_location import VehicleLocation
from mobility_manager.domain.exceptions import VehicleLocationNotFoundError


class InMemoryLocationRepo:
    def __init__(self, location: VehicleLocation | None = None) -> None:
        self._location = location

    def save(self, location: VehicleLocation) -> None:
        self._location = location

    def get_latest(self, vehicle_id) -> VehicleLocation | None:
        return self._location


def _make_location(vehicle_id=None) -> VehicleLocation:
    if vehicle_id is None:
        vehicle_id = uuid4()
    return VehicleLocation(
        id=uuid4(),
        vehicle_id=vehicle_id,
        latitude=40.4,
        longitude=-3.7,
        recorded_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
        source="pull",
    )


def test_returns_location_when_found() -> None:
    location = _make_location()
    repo = InMemoryLocationRepo(location=location)
    uc = GetLatestVehicleLocation(location_repo=repo)

    result = uc.execute(location.vehicle_id)

    assert result == location


def test_raises_when_no_location_history() -> None:
    repo = InMemoryLocationRepo(location=None)
    uc = GetLatestVehicleLocation(location_repo=repo)

    with pytest.raises(VehicleLocationNotFoundError):
        uc.execute(uuid4())


def test_unknown_vehicle_also_raises() -> None:
    """get_latest returns None for unknown vehicle; use case raises the same error."""
    repo = InMemoryLocationRepo(location=None)
    uc = GetLatestVehicleLocation(location_repo=repo)

    with pytest.raises(VehicleLocationNotFoundError):
        uc.execute(uuid4())
