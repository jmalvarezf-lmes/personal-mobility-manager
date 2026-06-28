"""
Unit tests for Brand enum.
"""

import pytest

from mobility_manager.domain.value_objects.brand import Brand


def test_toyota_value() -> None:
    assert Brand.TOYOTA.value == "toyota"


def test_generic_value() -> None:
    assert Brand.GENERIC.value == "generic"


def test_brand_from_string_toyota() -> None:
    assert Brand("toyota") == Brand.TOYOTA


def test_brand_from_string_generic() -> None:
    assert Brand("generic") == Brand.GENERIC


def test_invalid_brand_raises_value_error() -> None:
    with pytest.raises(ValueError):
        Brand("bmw")


def test_brand_is_str() -> None:
    assert isinstance(Brand.TOYOTA, str)
    assert Brand.TOYOTA == "toyota"


def test_brand_enum_members() -> None:
    members = {b.value for b in Brand}
    assert members == {"toyota", "generic"}
