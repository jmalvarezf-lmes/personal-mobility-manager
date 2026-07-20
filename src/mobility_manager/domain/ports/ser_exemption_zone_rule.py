"""
Port (interface): SerExemptionZoneRule.

Abstract contract for deciding whether a given SerZone qualifies for SER
exemption eligibility at all, independent of whether any vehicle actually
has a stored exemption — see add-ser-exemption-zone-rule design.md.
"""

from abc import ABC, abstractmethod

from mobility_manager.domain.entities.ser_zone import SerZone


class SerExemptionZoneRule(ABC):
    """Abstract port for evaluating per-city SER exemption zone eligibility."""

    @abstractmethod
    def is_zone_eligible(self, zone: SerZone) -> bool:
        """
        Return whether `zone` qualifies for SER exemption eligibility at all.

        This is a fact about the zone itself (e.g. Madrid's green-zone-only
        rule), evaluated independently of any vehicle's stored exemption —
        see design.md's Decisions section.
        """
        ...
