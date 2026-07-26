"""
Port (interface): SerLabelExemptionRule.

Abstract contract for deciding whether a given DGT ambient label is SER-exempt
in a given city, independent of any vehicle's stored manual exemption or the
zone's own eligibility — see add-ser-label-exemption-rule design.md.
"""

from abc import ABC, abstractmethod

from mobility_manager.domain.value_objects.ambient_label import AmbientLabel


class SerLabelExemptionRule(ABC):
    """Abstract port for evaluating per-city SER ambient-label exemption."""

    @abstractmethod
    def is_label_exempt(self, city_code: str, label: AmbientLabel) -> bool:
        """
        Return whether `label` is SER-exempt for `city_code`.

        This is a fact about the DGT ambient label itself (e.g. label `0`,
        electric, being nationally exempt from paid parking), evaluated
        independently of any vehicle's stored manual exemption or the zone's
        own eligibility — see design.md's Decisions section.
        """
        ...
