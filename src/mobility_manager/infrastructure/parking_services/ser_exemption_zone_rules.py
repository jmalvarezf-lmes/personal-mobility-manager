"""
Infrastructure implementation: CitySerExemptionZoneRule.

A single, hardcoded, pure (no I/O) dispatcher of per-city SER exemption
zone eligibility rules — see add-ser-exemption-zone-rule design.md
Decisions ("single injected port, one dispatching implementation").
"""

from collections.abc import Callable

from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.ports.ser_exemption_zone_rule import SerExemptionZoneRule
from mobility_manager.infrastructure.parking_services.madrid.zone_type import MadridZoneType


def _madrid_is_eligible(zone: SerZone) -> bool:
    return zone.zone_type == MadridZoneType.Verde.display_name


_CITY_RULES: dict[str, Callable[[SerZone], bool]] = {
    "madrid": _madrid_is_eligible,
}


class CitySerExemptionZoneRule(SerExemptionZoneRule):
    """Dispatches per `zone.city_code`; unknown/other cities default to always-eligible."""

    def is_zone_eligible(self, zone: SerZone) -> bool:
        rule = _CITY_RULES.get(zone.city_code)
        return rule(zone) if rule is not None else True
