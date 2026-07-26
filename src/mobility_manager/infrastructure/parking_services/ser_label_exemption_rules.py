"""
Infrastructure implementation: CitySerLabelExemptionRule.

A single, hardcoded, pure (no I/O) dispatcher of per-city SER ambient-label
exemption rules — see add-ser-label-exemption-rule design.md Decision 1
("single injected port, one dispatching implementation", mirroring
`ser_exemption_zone_rules.py`).

Every city currently shares the same rule (label `0`, electric, is exempt),
including unconfigured cities (design.md Decision 4) — the port exists as
the designated seam for a future city-specific carve-out, not because
behavior varies today.
"""

from collections.abc import Callable

from mobility_manager.domain.ports.ser_label_exemption_rule import SerLabelExemptionRule
from mobility_manager.domain.value_objects.ambient_label import AmbientLabel


def _madrid_is_exempt(label: AmbientLabel) -> bool:
    return label == AmbientLabel.ZERO


_CITY_RULES: dict[str, Callable[[AmbientLabel], bool]] = {
    "madrid": _madrid_is_exempt,
}


class CitySerLabelExemptionRule(SerLabelExemptionRule):
    """Dispatches per `city_code`; unknown/other cities default to the same electric-exempt rule."""

    def is_label_exempt(self, city_code: str, label: AmbientLabel) -> bool:
        rule = _CITY_RULES.get(city_code)
        return rule(label) if rule is not None else label == AmbientLabel.ZERO
