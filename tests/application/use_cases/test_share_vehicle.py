"""
Unit tests for ShareVehicle use case.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from mobility_manager.application.use_cases.share_vehicle import (
    ShareVehicle,
    ShareVehicleResult,
)
from mobility_manager.domain.entities.user import User
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.entities.vehicle_share import VehicleShare
from mobility_manager.domain.exceptions import UserNotFoundError, VehicleNotFoundError
from mobility_manager.domain.value_objects.brand import Brand


class FakeVehicleRepo:
    def __init__(self, vehicle: Vehicle | None = None) -> None:
        self._vehicle = vehicle

    def get_by_id(self, vehicle_id: UUID) -> Vehicle | None:
        return self._vehicle


class FakeUserRepo:
    def __init__(self, user: User | None = None) -> None:
        self._user = user

    def find_by_email(self, email: str) -> User | None:
        return self._user


class FakeShareRepo:
    def __init__(self) -> None:
        self.saved: list[VehicleShare] = []

    def save(self, share: VehicleShare) -> None:
        self.saved.append(share)

    def find_by_vehicle_and_user(self, vehicle_id: UUID, user_id: UUID) -> VehicleShare | None:
        return None


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


def _make_user(user_id: UUID, email: str = "sharee@example.com") -> User:
    return User(
        id=user_id,
        google_sub="sub",
        email=email,
        display_name="Sharee",
        created_at=datetime.now(UTC),
    )


def test_share_vehicle_saves_share_and_returns_result() -> None:
    owner_id = uuid4()
    sharee_id = uuid4()
    vehicle = _make_vehicle(owner_id)
    sharee = _make_user(sharee_id)

    vehicle_repo = FakeVehicleRepo(vehicle)
    user_repo = FakeUserRepo(sharee)
    share_repo = FakeShareRepo()
    use_case = ShareVehicle(vehicle_repo, user_repo, share_repo)

    result = use_case.execute(vehicle.id, owner_id, sharee.email)

    assert isinstance(result, ShareVehicleResult)
    assert result.user_id == sharee_id
    assert result.display_name == "Sharee"
    assert result.email == sharee.email
    assert result.created_at == share_repo.saved[0].created_at
    assert len(share_repo.saved) == 1
    assert share_repo.saved[0].vehicle_id == vehicle.id
    assert share_repo.saved[0].user_id == sharee_id


def test_share_vehicle_not_found_raises() -> None:
    owner_id = uuid4()
    vehicle_repo = FakeVehicleRepo(None)
    user_repo = FakeUserRepo(_make_user(uuid4()))
    share_repo = FakeShareRepo()
    use_case = ShareVehicle(vehicle_repo, user_repo, share_repo)

    with pytest.raises(VehicleNotFoundError):
        use_case.execute(uuid4(), owner_id, "sharee@example.com")


def test_share_vehicle_not_owned_raises() -> None:
    owner_id = uuid4()
    other_user_id = uuid4()
    vehicle = _make_vehicle(other_user_id)
    sharee = _make_user(uuid4())

    vehicle_repo = FakeVehicleRepo(vehicle)
    user_repo = FakeUserRepo(sharee)
    share_repo = FakeShareRepo()
    use_case = ShareVehicle(vehicle_repo, user_repo, share_repo)

    with pytest.raises(VehicleNotFoundError):
        use_case.execute(vehicle.id, owner_id, sharee.email)


def test_share_vehicle_user_not_found_raises() -> None:
    owner_id = uuid4()
    vehicle = _make_vehicle(owner_id)
    vehicle_repo = FakeVehicleRepo(vehicle)
    user_repo = FakeUserRepo(None)
    share_repo = FakeShareRepo()
    use_case = ShareVehicle(vehicle_repo, user_repo, share_repo)

    with pytest.raises(UserNotFoundError):
        use_case.execute(vehicle.id, owner_id, "unknown@example.com")


def test_share_vehicle_self_share_raises() -> None:
    owner_id = uuid4()
    vehicle = _make_vehicle(owner_id)
    owner = _make_user(owner_id, email="owner@example.com")

    vehicle_repo = FakeVehicleRepo(vehicle)
    user_repo = FakeUserRepo(owner)
    share_repo = FakeShareRepo()
    use_case = ShareVehicle(vehicle_repo, user_repo, share_repo)

    with pytest.raises(ValueError, match="Owner cannot share a vehicle with themselves"):
        use_case.execute(vehicle.id, owner_id, owner.email)
