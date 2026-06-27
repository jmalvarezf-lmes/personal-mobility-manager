"""
Unit tests for ZoneType base class and MadridZoneType implementation.
"""
import pytest

from mobility_manager.domain.value_objects.zone_type import ZoneType
from mobility_manager.infrastructure.parking_services.madrid.zone_type import (
    MadridZoneType,
)


# ---------------------------------------------------------------------------
# ZoneType contract enforcement (raises NotImplementedError when not implemented)
# ---------------------------------------------------------------------------

class _IncompleteZoneType(ZoneType):
    """Subclass that forgets to implement display_name and from_raw."""
    pass


def test_display_name_raises_when_not_implemented() -> None:
    instance = _IncompleteZoneType()
    with pytest.raises(NotImplementedError):
        _ = instance.display_name


def test_from_raw_raises_when_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        _IncompleteZoneType.from_raw("Azul")


# ---------------------------------------------------------------------------
# MadridZoneType: from_raw()
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Azul", MadridZoneType.Azul),
        ("Verde", MadridZoneType.Verde),
        ("Alta Rotación", MadridZoneType.AltaRotacion),
        ("Naranja", MadridZoneType.Naranja),
        ("Rojo", MadridZoneType.Rojo),
    ],
)
def test_from_raw_returns_correct_member(raw: str, expected: MadridZoneType) -> None:
    result = MadridZoneType.from_raw(raw)
    assert result is expected


def test_from_raw_returns_none_for_unknown_value() -> None:
    result = MadridZoneType.from_raw("Morado")
    assert result is None


def test_from_raw_returns_none_for_empty_string() -> None:
    result = MadridZoneType.from_raw("")
    assert result is None


def test_from_raw_is_case_sensitive() -> None:
    result = MadridZoneType.from_raw("azul")
    assert result is None


# ---------------------------------------------------------------------------
# MadridZoneType: display_name
# ---------------------------------------------------------------------------

def test_display_name_equals_value() -> None:
    assert MadridZoneType.Azul.display_name == "Azul"
    assert MadridZoneType.Verde.display_name == "Verde"
    assert MadridZoneType.AltaRotacion.display_name == "Alta Rotación"
    assert MadridZoneType.Naranja.display_name == "Naranja"
    assert MadridZoneType.Rojo.display_name == "Rojo"


# ---------------------------------------------------------------------------
# MadridZoneType: is a subclass of ZoneType
# ---------------------------------------------------------------------------

def test_madrid_zone_type_is_subclass_of_zone_type() -> None:
    assert issubclass(MadridZoneType, ZoneType)
    assert isinstance(MadridZoneType.Azul, ZoneType)
