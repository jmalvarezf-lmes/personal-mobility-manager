"""
Unit tests for ListVehicleShares use case.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from mobility_manager.application.use_cases.list_vehicle_shares import (
    ListVehicleShares,
    VehicleSharee,
)
from mobility_manager.domain.entities.user import User
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.entities.vehicle_share import VehicleShare
from mobility_manager.domain.exceptions import VehicleNotFoundError
from mobility_manager.domain.value_objects.brand import Brand


class FakeVehicleRepo:
    def __init__(self, vehicle: Vehicle | None = None) -> None:
        self._vehicle = vehicle

    def get_by_id(self, vehicle_id: UUID) -> Vehicle | None:
        return self._vehicle


class FakeShareRepo:
    def __init__(self, shares: list[VehicleShare] | None = None) -> None:
        self._shares = shares or []

    def list_sharees(self, vehicle_id: UUID) -> list[VehicleShare]:
        return self._shares


class FakeUserRepo:
    def __init__(self, users: dict[UUID, User] | None = None) -> None:
        self._users = users or {}

    def find_by_id(self, user_id: UUID) -> User | None:
        return self._users.get(user_id)


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


def _make_user(user_id: UUID, email: str) -> User:
    return User(
        id=user_id,
        google_sub="sub",
        email=email,
        display_name="Sharee",
        created_at=datetime.now(UTC),
    )


def test_list_vehicle_shares_returns_sharee_details() -> None:
    owner_id = uuid4()
    sharee_id = uuid4()
    vehicle = _make_vehicle(owner_id)
    sharee = _make_user(sharee_id, "sharee@example.com")
    share = VehicleShare(
        vehicle_id=vehicle.id,
        user_id=sharee_id,
        created_at=datetime.now(UTC),
    )

    use_case = ListVehicleShares(
        vehicle_repo=FakeVehicleRepo(vehicle),
        share_repo=FakeShareRepo([share]),
        user_repo=FakeUserRepo({sharee_id: sharee}),
    )

    result = use_case.execute(vehicle.id, owner_id)

    assert result == [
        VehicleSharee(
            user_id=sharee_id,
            display_name="Sharee",
            email="sharee@example.com",
            created_at=share.created_at,
        )
    ]


def test_list_vehicle_shares_empty_when_no_shares() -> None:
    owner_id = uuid4()
    vehicle = _make_vehicle(owner_id)

    use_case = ListVehicleShares(
        vehicle_repo=FakeVehicleRepo(vehicle),
        share_repo=FakeShareRepo([]),
        user_repo=FakeUserRepo({}),
    )

    result = use_case.execute(vehicle.id, owner_id)

    assert result == []


def test_list_vehicle_shares_skips_missing_users() -> None:
    owner_id = uuid4()
    sharee_id = uuid4()
    vehicle = _make_vehicle(owner_id)
    share = VehicleShare(
        vehicle_id=vehicle.id,
        user_id=sharee_id,
        created_at=datetime.now(UTC),
    )

    use_case = ListVehicleShares(
        vehicle_repo=FakeVehicleRepo(vehicle),
        share_repo=FakeShareRepo([share]),
        user_repo=FakeUserRepo({}),
    )

    result = use_case.execute(vehicle.id, owner_id)

    assert result == []


def test_list_vehicle_shares_not_owner_raises() -> None:
    owner_id = uuid4()
    other_id = uuid4()
    vehicle = _make_vehicle(owner_id)

    use_case = ListVehicleShares(
        vehicle_repo=FakeVehicleRepo(vehicle),
        share_repo=FakeShareRepo([]),
        user_repo=FakeUserRepo({}),
    )

    with pytest.raises(VehicleNotFoundError):
        use_case.execute(vehicle.id, other_id)


def test_list_vehicle_shares_vehicle_not_found_raises() -> None:
    owner_id = uuid4()

    use_case = ListVehicleShares(
        vehicle_repo=FakeVehicleRepo(None),
        share_repo=FakeShareRepo([]),
        user_repo=FakeUserRepo({}),
    )

    with pytest.raises(VehicleNotFoundError):
        use_case.execute(uuid4(), owner_id)
