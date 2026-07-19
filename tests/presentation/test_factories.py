"""
Unit tests for VehicleRegisterFactory and VehicleUpdateFactory.
"""

from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.presentation.api.factories import (
    VehicleRegisterFactory,
    VehicleUpdateFactory,
)
from mobility_manager.presentation.api.schemas import (
    RegisterGenericRequest,
    RegisterToyotaRequest,
    UpdateGenericRequest,
    UpdateToyotaRequest,
)


class TestVehicleRegisterFactory:
    def test_toyota_body_builds_toyota_config(self) -> None:
        body = RegisterToyotaRequest(
            brand=Brand.TOYOTA,
            display_name="My Toyota",
            vin="1HGCM82633A004352",
            username="alice",
            password="secret",
            locale="en_GB",
        )
        result = VehicleRegisterFactory.build(body)

        assert result.brand == Brand.TOYOTA
        assert result.display_name == "My Toyota"
        assert result.vin == "1HGCM82633A004352"
        assert result.toyota_config is not None
        assert result.toyota_config.username == "alice"
        assert result.toyota_config.password == "secret"
        assert result.toyota_config.locale == "en_GB"
        assert result.toyota_config.vin == "1HGCM82633A004352"

    def test_generic_body_yields_no_toyota_config(self) -> None:
        body = RegisterGenericRequest(
            brand=Brand.GENERIC,
            display_name="My Generic",
        )
        result = VehicleRegisterFactory.build(body)

        assert result.brand == Brand.GENERIC
        assert result.display_name == "My Generic"
        assert result.vin is None
        assert result.toyota_config is None


class TestVehicleUpdateFactory:
    def test_toyota_body_extracts_credentials(self) -> None:
        body = UpdateToyotaRequest(
            brand=Brand.TOYOTA,
            display_name="Updated Toyota",
            username="alice",
            locale="en_GB",
            password="new_pass",
            license_plate="1234ABC",
        )
        result = VehicleUpdateFactory.build(body)

        assert result.display_name == "Updated Toyota"
        assert result.username == "alice"
        assert result.locale == "en_GB"
        assert result.password == "new_pass"
        assert result.license_plate == "1234ABC"

    def test_toyota_body_with_null_password(self) -> None:
        body = UpdateToyotaRequest(
            brand=Brand.TOYOTA,
            display_name="Updated Toyota",
            username="alice",
            locale="en_GB",
            password=None,
            license_plate=None,
        )
        result = VehicleUpdateFactory.build(body)

        assert result.password is None
        assert result.license_plate is None

    def test_generic_body_yields_none_credentials(self) -> None:
        body = UpdateGenericRequest(
            brand=Brand.GENERIC,
            display_name="Updated Generic",
            license_plate="XYZ789",
        )
        result = VehicleUpdateFactory.build(body)

        assert result.display_name == "Updated Generic"
        assert result.username is None
        assert result.locale is None
        assert result.password is None
        assert result.license_plate == "XYZ789"

    def test_generic_body_with_no_license_plate(self) -> None:
        body = UpdateGenericRequest(
            brand=Brand.GENERIC,
            display_name="Generic",
        )
        result = VehicleUpdateFactory.build(body)

        assert result.license_plate is None
