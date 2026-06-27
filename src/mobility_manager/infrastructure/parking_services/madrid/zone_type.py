"""
Madrid-specific parking zone type classifications.

MadridZoneType inherits from both ZoneType (domain contract) and str+Enum
(standard Python enum with string values). The MRO works without a combined
metaclass because ZoneType is a plain class (type metaclass), and EnumType
(str+Enum path) wins the metaclass resolution cleanly.
"""
from enum import Enum

from mobility_manager.domain.value_objects.zone_type import ZoneType


_MADRID_COLOURS: dict[str, str] = {
    "Azul": "#2563EB",
    "Verde": "#16A34A",
}


class MadridZoneType(ZoneType, str, Enum):
    """Madrid SER parking zone type classification."""

    Azul = "Azul"
    Verde = "Verde"
    AltaRotacion = "Alta Rotación"
    Naranja = "Naranja"
    Rojo = "Rojo"

    @property
    def display_name(self) -> str:
        return self.value

    @property
    def colour(self) -> str:
        return _MADRID_COLOURS.get(self.value, "#6B7280")

    @classmethod
    def from_raw(cls, raw: str) -> "MadridZoneType | None":
        """
        Parse a raw zone type string from the CSV source.

        Accepts the plain colour name after the RGB prefix has been stripped
        (e.g. "Azul", "Alta Rotación"). Returns None for unrecognised values.
        """
        try:
            return cls(raw)
        except ValueError:
            return None
