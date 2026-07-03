"""
Unit tests for LicensePlate value object.
"""

import pytest

from mobility_manager.domain.value_objects.license_plate import LicensePlate


class TestLicensePlate:
    def test_valid_construction(self) -> None:
        lp = LicensePlate(value="1234ABC")
        assert lp.value == "1234ABC"

    def test_exactly_max_length_is_valid(self) -> None:
        value = "A" * LicensePlate.MAX_LENGTH
        lp = LicensePlate(value=value)
        assert lp.value == value

    def test_too_long_raises_value_error(self) -> None:
        too_long = "A" * (LicensePlate.MAX_LENGTH + 1)
        with pytest.raises(ValueError, match="exceeds maximum length"):
            LicensePlate(value=too_long)

    def test_is_frozen(self) -> None:
        lp = LicensePlate(value="ABC123")
        with pytest.raises((AttributeError, TypeError)):
            lp.value = "NEW"  # type: ignore[misc]

    def test_empty_string_is_valid(self) -> None:
        lp = LicensePlate(value="")
        assert lp.value == ""
