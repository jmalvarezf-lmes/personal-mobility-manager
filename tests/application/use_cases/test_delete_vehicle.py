"""
Unit tests for DeleteVehicle use case.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from mobility_manager.application.use_cases.delete_vehicle import DeleteVehicle
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.exceptions import VehicleNotFoundError
from mobility_manager.domain.value_objects.brand import Brand

_OWNER_ID = uuid4()


def _make_vehicle(owner_id: UUID | None = None) -> Vehicle:
    return Vehicle(
        id=uuid4(),
        brand=Brand.GENERIC,
        display_name="Test Car",
        vin=None,
        created_at=datetime.now(UTC),
        user_id=owner_id or _OWNER_ID,
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
        pass


class TestDeleteVehicle:
    def test_delete_removes_vehicle(self) -> None:
        repo = InMemoryVehicleRepo()
        vehicle = _make_vehicle()
        repo.save(vehicle)
        uc = DeleteVehicle(vehicle_repo=repo)

        uc.execute(vehicle.id)

        assert repo.get_by_id(vehicle.id) is None

    def test_delete_not_found_raises(self) -> None:
        repo = InMemoryVehicleRepo()
        uc = DeleteVehicle(vehicle_repo=repo)

        with pytest.raises(VehicleNotFoundError):
            uc.execute(uuid4())

    def test_delete_only_affects_target_vehicle(self) -> None:
        repo = InMemoryVehicleRepo()
        v1 = _make_vehicle()
        v2 = _make_vehicle()
        repo.save(v1)
        repo.save(v2)
        uc = DeleteVehicle(vehicle_repo=repo)

        uc.execute(v1.id)

        assert repo.get_by_id(v1.id) is None
        assert repo.get_by_id(v2.id) is not None
