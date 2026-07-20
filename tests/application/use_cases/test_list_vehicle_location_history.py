"""
Unit tests for ListVehicleLocationHistory use case.

Note: ownership is not checked at this layer — see the router's
`require_owned_vehicle` dependency (mirrors GetLatestVehicleLocation, which
is also a thin wrapper with no ownership logic of its own). These tests
therefore cover the pagination delegation itself, not 401/403/404, which are
covered by the router integration tests instead.
"""

from datetime import UTC, datetime
from uuid import uuid4

from mobility_manager.application.use_cases.list_vehicle_location_history import (
    ListVehicleLocationHistory,
)
from mobility_manager.domain.entities.vehicle_location import VehicleLocation


class InMemoryLocationRepo:
    def __init__(self, history: list[VehicleLocation] | None = None) -> None:
        self._history = history or []
        self.last_call: tuple[object, ...] | None = None

    def list_history(self, vehicle_id, limit, offset) -> tuple[list[VehicleLocation], bool]:
        self.last_call = (vehicle_id, limit, offset)
        page = self._history[offset : offset + limit]
        has_more = offset + limit < len(self._history)
        return page, has_more


def _make_location(vehicle_id=None) -> VehicleLocation:
    if vehicle_id is None:
        vehicle_id = uuid4()
    return VehicleLocation(
        id=uuid4(),
        vehicle_id=vehicle_id,
        latitude=40.4,
        longitude=-3.7,
        recorded_at=datetime.now(UTC),
        received_at=datetime.now(UTC),
        source="pull",
    )


def test_returns_page_and_has_more_from_repo() -> None:
    vehicle_id = uuid4()
    history = [_make_location(vehicle_id) for _ in range(3)]
    repo = InMemoryLocationRepo(history=history)
    uc = ListVehicleLocationHistory(location_repo=repo)

    items, has_more = uc.execute(vehicle_id, limit=5, offset=0)

    assert items == history
    assert has_more is False


def test_delegates_limit_and_offset_to_repo() -> None:
    vehicle_id = uuid4()
    repo = InMemoryLocationRepo(history=[])
    uc = ListVehicleLocationHistory(location_repo=repo)

    uc.execute(vehicle_id, limit=5, offset=10)

    assert repo.last_call == (vehicle_id, 5, 10)


def test_vehicle_with_no_history_returns_empty_page() -> None:
    """A vehicle with no recorded locations returns an empty page, not an error."""
    repo = InMemoryLocationRepo(history=[])
    uc = ListVehicleLocationHistory(location_repo=repo)

    items, has_more = uc.execute(uuid4(), limit=5, offset=0)

    assert items == []
    assert has_more is False
