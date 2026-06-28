"""
Unit tests for RegisterVehicle use case.
"""
from uuid import UUID

import pytest

from mobility_manager.application.use_cases.register_vehicle import RegisterVehicle
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.exceptions import BrandNotEnabledError
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.domain.value_objects.generic_config import GenericConfig
from mobility_manager.domain.value_objects.toyota_config import ToyotaConfig


class InMemoryVehicleRepo:
    def __init__(self) -> None:
        self.saved: list[Vehicle] = []

    def save(self, vehicle: Vehicle) -> None:
        self.saved.append(vehicle)

    def get_by_id(self, vehicle_id: UUID) -> Vehicle | None:
        return next((v for v in self.saved if v.id == vehicle_id), None)

    def get_all_by_brand(self, brand: Brand) -> list[Vehicle]:
        return [v for v in self.saved if v.brand == brand]


class InMemoryConfigRepo:
    def __init__(self) -> None:
        self.toyota: dict[UUID, ToyotaConfig] = {}
        self.generic: dict[UUID, GenericConfig] = {}

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


def _make_use_case(
    enabled: list[Brand] | None = None,
) -> tuple[RegisterVehicle, InMemoryVehicleRepo, InMemoryConfigRepo]:
    if enabled is None:
        enabled = [Brand.TOYOTA, Brand.GENERIC]
    v_repo = InMemoryVehicleRepo()
    c_repo = InMemoryConfigRepo()
    uc = RegisterVehicle(vehicle_repo=v_repo, config_repo=c_repo, enabled_brands=enabled)
    return uc, v_repo, c_repo


class TestGenericRegistration:
    def test_generic_vehicle_saved(self) -> None:
        uc, v_repo, _ = _make_use_case(enabled=[Brand.GENERIC])
        uc.execute(Brand.GENERIC, "My Car")
        assert len(v_repo.saved) == 1
        assert v_repo.saved[0].brand == Brand.GENERIC

    def test_generic_result_has_location_token(self) -> None:
        uc, _, _ = _make_use_case(enabled=[Brand.GENERIC])
        result = uc.execute(Brand.GENERIC, "My Car")
        assert result.location_token is not None
        assert len(result.location_token) == 36  # UUID format

    def test_generic_token_is_unique_per_registration(self) -> None:
        uc, _, _ = _make_use_case(enabled=[Brand.GENERIC])
        r1 = uc.execute(Brand.GENERIC, "Car 1")
        r2 = uc.execute(Brand.GENERIC, "Car 2")
        assert r1.location_token != r2.location_token

    def test_generic_config_stored(self) -> None:
        uc, _, c_repo = _make_use_case(enabled=[Brand.GENERIC])
        result = uc.execute(Brand.GENERIC, "My Car")
        config = c_repo.get_generic_config(result.vehicle_id)
        assert config is not None
        assert config.location_token == result.location_token

    def test_generic_vin_is_none(self) -> None:
        uc, _, _ = _make_use_case(enabled=[Brand.GENERIC])
        result = uc.execute(Brand.GENERIC, "My Car")
        assert result.vin is None


class TestToyotaRegistration:
    def _toyota_config(self) -> ToyotaConfig:
        return ToyotaConfig(username="user", password="pass", locale="en_GB", vin="VIN123")

    def test_toyota_vehicle_saved(self) -> None:
        uc, v_repo, _ = _make_use_case(enabled=[Brand.TOYOTA])
        uc.execute(Brand.TOYOTA, "My Toyota", vin="VIN123", toyota_config=self._toyota_config())
        assert v_repo.saved[0].brand == Brand.TOYOTA

    def test_toyota_no_location_token(self) -> None:
        uc, _, _ = _make_use_case(enabled=[Brand.TOYOTA])
        result = uc.execute(
            Brand.TOYOTA, "My Toyota", vin="VIN123", toyota_config=self._toyota_config()
        )
        assert result.location_token is None

    def test_toyota_vin_on_result(self) -> None:
        uc, _, _ = _make_use_case(enabled=[Brand.TOYOTA])
        result = uc.execute(
            Brand.TOYOTA, "My Toyota", vin="VIN123", toyota_config=self._toyota_config()
        )
        assert result.vin == "VIN123"

    def test_toyota_config_stored(self) -> None:
        uc, _, c_repo = _make_use_case(enabled=[Brand.TOYOTA])
        result = uc.execute(
            Brand.TOYOTA, "My Toyota", vin="VIN123", toyota_config=self._toyota_config()
        )
        config = c_repo.get_toyota_config(result.vehicle_id)
        assert config.username == "user"
        assert config.vin == "VIN123"

    def test_toyota_missing_config_raises(self) -> None:
        uc, _, _ = _make_use_case(enabled=[Brand.TOYOTA])
        with pytest.raises(ValueError, match="toyota_config"):
            uc.execute(Brand.TOYOTA, "My Toyota", vin="VIN123", toyota_config=None)


class TestBrandGating:
    def test_disabled_brand_raises(self) -> None:
        uc, _, _ = _make_use_case(enabled=[Brand.GENERIC])
        with pytest.raises(BrandNotEnabledError):
            uc.execute(Brand.TOYOTA, "My Toyota", vin="V1")

    def test_empty_enabled_brands_rejects_all(self) -> None:
        uc, _, _ = _make_use_case(enabled=[])
        with pytest.raises(BrandNotEnabledError):
            uc.execute(Brand.GENERIC, "Car")

    def test_result_brand_matches_input(self) -> None:
        uc, _, _ = _make_use_case(enabled=[Brand.GENERIC])
        result = uc.execute(Brand.GENERIC, "Car")
        assert result.brand == Brand.GENERIC
