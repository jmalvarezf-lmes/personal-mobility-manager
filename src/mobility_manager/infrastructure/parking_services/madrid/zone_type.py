"""
Madrid-specific parking zone type classifications.

MadridZoneType inherits from both ZoneType (domain contract) and StrEnum
(standard Python string enum). The MRO works without a combined metaclass
because ZoneType is a plain class (type metaclass), and EnumType from
StrEnum wins the metaclass resolution cleanly.
"""

from __future__ import annotations

from enum import StrEnum

from mobility_manager.domain.value_objects.zone_type import ZoneType

_MADRID_COLOURS: dict[str, str] = {
    "Azul": "#2563EB",
    "Verde": "#16A34A",
    "Naranja": "#F97316",
    "Rojo": "#DC2626",
    "Alta Rotación": "#7C3AED",
}


class MadridZoneType(ZoneType, StrEnum):
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
    def from_raw(cls, raw: str) -> MadridZoneType | None:
        """
        Parse a raw zone type string.

        Accepts an already-plain colour name (e.g. "Azul", "Alta Rotación"),
        as produced by the SHP source's `Color` field. The retired 218228 CSV
        source used to prefix this value with an RGB triple (e.g.
        "043000255 Azul"), which callers had to strip before calling this
        method; that stripping is no longer relevant since that source was
        removed. Returns None for unrecognised values.
        """
        try:
            return cls(raw)
        except ValueError:
            return None
