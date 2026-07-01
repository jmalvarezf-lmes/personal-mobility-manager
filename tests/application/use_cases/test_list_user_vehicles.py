"""
Unit tests for ListUserVehicles use case.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from mobility_manager.application.use_cases.list_user_vehicles import (
    ListUserVehicles,
    VehicleWithLocation,
)
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.entities.vehicle_location import VehicleLocation
from mobility_manager.domain.value_objects.brand import Brand

_USER_A = uuid4()
_USER_B = uuid4()


def _make_vehicle(user_id: UUID, brand: Brand = Brand.GENERIC) -> Vehicle:
    return Vehicle(
        id=uuid4(),
        brand=brand,
        display_name="Test Car",
        vin=None,
        created_at=datetime.now(UTC),
        user_id=user_id,
    )


def _make_location(vehicle_id: UUID) -> VehicleLocation:
    return VehicleLocation(
        id=uuid4(),
        vehicle_id=vehicle_id,
        latitude=40.4168,
        longitude=-3.7038,
        recorded_at=datetime.now(UTC),
        received_at=datetime.now(UTC),
        source="push",  # type: ignore[arg-type]
    )


class InMemoryVehicleRepo:
    def __init__(self) -> None:
        self.vehicles: list[Vehicle] = []

    def save(self, vehicle: Vehicle) -> None:
        self.vehicles.append(vehicle)

    def get_by_id(self, vehicle_id: UUID) -> Vehicle | None:
        return next((v for v in self.vehicles if v.id == vehicle_id), None)

    def find_by_id(self, vehicle_id: UUID) -> Vehicle | None:
        return self.get_by_id(vehicle_id)

    def get_all_by_brand(self, brand: Brand) -> list[Vehicle]:
        return [v for v in self.vehicles if v.brand == brand]

    def get_all_by_user_id(self, user_id: UUID) -> list[Vehicle]:
        return [v for v in self.vehicles if v.user_id == user_id]

    def delete(self, vehicle_id: UUID) -> None:
        self.vehicles = [v for v in self.vehicles if v.id != vehicle_id]

    def update_display_name(self, vehicle_id: UUID, display_name: str) -> None:
        for v in self.vehicles:
            if v.id == vehicle_id:
                object.__setattr__(v, "display_name", display_name)


class InMemoryLocationRepo:
    def __init__(self) -> None:
        self.locations: dict[UUID, VehicleLocation] = {}

    def save(self, location: VehicleLocation) -> None:
        self.locations[location.vehicle_id] = location

    def get_latest(self, vehicle_id: UUID) -> VehicleLocation | None:
        return self.locations.get(vehicle_id)


def _make_use_case() -> tuple[ListUserVehicles, InMemoryVehicleRepo, InMemoryLocationRepo]:
    v_repo = InMemoryVehicleRepo()
    l_repo = InMemoryLocationRepo()
    uc = ListUserVehicles(vehicle_repo=v_repo, location_repo=l_repo)
    return uc, v_repo, l_repo


class TestListUserVehicles:
    def test_empty_list_when_no_vehicles(self) -> None:
        uc, _, _ = _make_use_case()
        result = uc.execute(_USER_A)
        assert result == []

    def test_returns_vehicles_for_user(self) -> None:
        uc, v_repo, _ = _make_use_case()
        v1 = _make_vehicle(_USER_A)
        v2 = _make_vehicle(_USER_A)
        v_repo.save(v1)
        v_repo.save(v2)

        result = uc.execute(_USER_A)
        assert len(result) == 2
        assert all(isinstance(r, VehicleWithLocation) for r in result)

    def test_vehicle_without_location_has_none(self) -> None:
        uc, v_repo, _ = _make_use_case()
        v = _make_vehicle(_USER_A)
        v_repo.save(v)

        result = uc.execute(_USER_A)
        assert len(result) == 1
        assert result[0].vehicle == v
        assert result[0].location is None

    def test_vehicle_with_location_populated(self) -> None:
        uc, v_repo, l_repo = _make_use_case()
        v = _make_vehicle(_USER_A)
        v_repo.save(v)
        loc = _make_location(v.id)
        l_repo.save(loc)

        result = uc.execute(_USER_A)
        assert result[0].location == loc

    def test_user_isolation(self) -> None:
        uc, v_repo, _ = _make_use_case()
        v_a = _make_vehicle(_USER_A)
        v_b = _make_vehicle(_USER_B)
        v_repo.save(v_a)
        v_repo.save(v_b)

        result_a = uc.execute(_USER_A)
        assert len(result_a) == 1
        assert result_a[0].vehicle.user_id == _USER_A

        result_b = uc.execute(_USER_B)
        assert len(result_b) == 1
        assert result_b[0].vehicle.user_id == _USER_B
