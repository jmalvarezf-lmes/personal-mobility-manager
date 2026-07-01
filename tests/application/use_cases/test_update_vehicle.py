"""
Unit tests for UpdateVehicle use case.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from mobility_manager.application.use_cases.update_vehicle import UpdateVehicle
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.exceptions import VehicleNotFoundError
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.domain.value_objects.generic_config import GenericConfig
from mobility_manager.domain.value_objects.toyota_config import ToyotaConfig

_OWNER_ID = uuid4()


def _make_vehicle(brand: Brand = Brand.GENERIC, owner_id: UUID | None = None) -> Vehicle:
    return Vehicle(
        id=uuid4(),
        brand=brand,
        display_name="Original Name",
        vin="VIN001" if brand == Brand.TOYOTA else None,
        created_at=datetime.now(UTC),
        user_id=owner_id or _OWNER_ID,
    )


class InMemoryVehicleRepo:
    def __init__(self) -> None:
        self.vehicles: list[Vehicle] = []
        self.display_names: dict[UUID, str] = {}

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
        self.display_names[vehicle_id] = display_name


class InMemoryConfigRepo:
    def __init__(self) -> None:
        self.toyota: dict[UUID, ToyotaConfig] = {}
        self.generic: dict[UUID, GenericConfig] = {}
        self.toyota_updates: list[tuple[UUID, ToyotaConfig]] = []

    def save_toyota_config(self, vehicle_id: UUID, config: ToyotaConfig) -> None:
        self.toyota[vehicle_id] = config

    def save_generic_config(self, vehicle_id: UUID, config: GenericConfig) -> None:
        self.generic[vehicle_id] = config

    def get_toyota_config(self, vehicle_id: UUID) -> ToyotaConfig:
        return self.toyota[vehicle_id]

    def get_generic_config(self, vehicle_id: UUID) -> GenericConfig | None:
        return self.generic.get(vehicle_id)

    def find_vehicle_by_token(self, token: str) -> UUID | None:
        for vid, cfg in self.generic.items():
            if cfg.location_token == token:
                return vid
        return None

    def update_toyota_config(self, vehicle_id: UUID, config: ToyotaConfig) -> None:
        self.toyota[vehicle_id] = config
        self.toyota_updates.append((vehicle_id, config))


def _make_use_case() -> tuple[UpdateVehicle, InMemoryVehicleRepo, InMemoryConfigRepo]:
    v_repo = InMemoryVehicleRepo()
    c_repo = InMemoryConfigRepo()
    uc = UpdateVehicle(vehicle_repo=v_repo, config_repo=c_repo)
    return uc, v_repo, c_repo


class TestUpdateVehicleGeneric:
    def test_updates_display_name(self) -> None:
        uc, v_repo, _ = _make_use_case()
        v = _make_vehicle(Brand.GENERIC)
        v_repo.save(v)

        uc.execute(v.id, display_name="New Name")

        assert v_repo.display_names[v.id] == "New Name"

    def test_generic_does_not_touch_config(self) -> None:
        uc, v_repo, c_repo = _make_use_case()
        v = _make_vehicle(Brand.GENERIC)
        v_repo.save(v)

        uc.execute(v.id, display_name="New Name")

        assert len(c_repo.toyota_updates) == 0

    def test_not_found_raises(self) -> None:
        uc, _, _ = _make_use_case()
        with pytest.raises(VehicleNotFoundError):
            uc.execute(uuid4(), display_name="Anything")


class TestUpdateVehicleToyota:
    def _setup_toyota(self) -> tuple[UpdateVehicle, InMemoryVehicleRepo, InMemoryConfigRepo, Vehicle]:
        uc, v_repo, c_repo = _make_use_case()
        v = _make_vehicle(Brand.TOYOTA)
        v_repo.save(v)
        c_repo.save_toyota_config(
            v.id,
            ToyotaConfig(username="alice", password="old_pass", locale="en_GB", vin="VIN001"),
        )
        return uc, v_repo, c_repo, v

    def test_updates_display_name_only_when_no_password(self) -> None:
        uc, v_repo, c_repo, v = self._setup_toyota()

        uc.execute(v.id, display_name="Updated", username="alice", locale="en_GB", password=None)

        assert v_repo.display_names[v.id] == "Updated"
        assert len(c_repo.toyota_updates) == 0

    def test_empty_password_does_not_re_encrypt(self) -> None:
        uc, v_repo, c_repo, v = self._setup_toyota()

        uc.execute(v.id, display_name="Updated", username="alice", locale="en_GB", password="")

        assert len(c_repo.toyota_updates) == 0

    def test_new_password_triggers_re_encryption(self) -> None:
        uc, v_repo, c_repo, v = self._setup_toyota()

        uc.execute(v.id, display_name="Updated", username="alice", locale="en_GB", password="new_pass")

        assert len(c_repo.toyota_updates) == 1
        _, updated_config = c_repo.toyota_updates[0]
        assert updated_config.password == "new_pass"

    def test_re_encryption_preserves_vin(self) -> None:
        uc, _, c_repo, v = self._setup_toyota()

        uc.execute(v.id, display_name="X", username="alice", locale="en_GB", password="new_pass")

        _, updated_config = c_repo.toyota_updates[0]
        assert updated_config.vin == "VIN001"

    def test_re_encryption_uses_existing_username_when_none_provided(self) -> None:
        uc, _, c_repo, v = self._setup_toyota()

        uc.execute(v.id, display_name="X", username=None, locale=None, password="new_pass")

        _, updated_config = c_repo.toyota_updates[0]
        assert updated_config.username == "alice"
        assert updated_config.locale == "en_GB"
