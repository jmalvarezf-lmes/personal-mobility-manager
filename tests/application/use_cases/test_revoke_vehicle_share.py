"""
Unit tests for RevokeVehicleShare use case.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from mobility_manager.application.use_cases.revoke_vehicle_share import RevokeVehicleShare
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.exceptions import VehicleNotFoundError
from mobility_manager.domain.value_objects.brand import Brand


class FakeVehicleRepo:
    def __init__(self, vehicle: Vehicle | None = None) -> None:
        self._vehicle = vehicle

    def get_by_id(self, vehicle_id: UUID) -> Vehicle | None:
        return self._vehicle


class FakeShareRepo:
    def __init__(self) -> None:
        self.deleted: list[tuple[UUID, UUID]] = []

    def delete(self, vehicle_id: UUID, user_id: UUID) -> None:
        self.deleted.append((vehicle_id, user_id))


def _make_vehicle(owner_id: UUID) -> Vehicle:
    return Vehicle(
        id=uuid4(),
        brand=Brand.GENERIC,
        display_name="Test Car",
        vin=None,
        license_plate=None,
        created_at=datetime.now(UTC),
        owner_id=owner_id,
    )


def test_owner_revokes_share() -> None:
    owner_id = uuid4()
    sharee_id = uuid4()
    vehicle = _make_vehicle(owner_id)

    vehicle_repo = FakeVehicleRepo(vehicle)
    share_repo = FakeShareRepo()
    use_case = RevokeVehicleShare(vehicle_repo, share_repo)

    use_case.execute(vehicle.id, owner_id, sharee_id)

    assert share_repo.deleted == [(vehicle.id, sharee_id)]


def test_sharee_revokes_own_share() -> None:
    owner_id = uuid4()
    sharee_id = uuid4()
    vehicle = _make_vehicle(owner_id)

    vehicle_repo = FakeVehicleRepo(vehicle)
    share_repo = FakeShareRepo()
    use_case = RevokeVehicleShare(vehicle_repo, share_repo)

    use_case.execute(vehicle.id, sharee_id, sharee_id)

    assert share_repo.deleted == [(vehicle.id, sharee_id)]


def test_non_owner_revoking_other_raises() -> None:
    owner_id = uuid4()
    sharee_id = uuid4()
    other_id = uuid4()
    vehicle = _make_vehicle(owner_id)

    vehicle_repo = FakeVehicleRepo(vehicle)
    share_repo = FakeShareRepo()
    use_case = RevokeVehicleShare(vehicle_repo, share_repo)

    with pytest.raises(PermissionError):
        use_case.execute(vehicle.id, other_id, sharee_id)

    assert share_repo.deleted == []


def test_vehicle_not_found_raises() -> None:
    vehicle_repo = FakeVehicleRepo(None)
    share_repo = FakeShareRepo()
    use_case = RevokeVehicleShare(vehicle_repo, share_repo)

    with pytest.raises(VehicleNotFoundError):
        use_case.execute(uuid4(), uuid4(), uuid4())
