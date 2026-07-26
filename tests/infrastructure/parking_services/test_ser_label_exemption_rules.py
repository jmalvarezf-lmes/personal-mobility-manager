"""
Unit tests for CitySerLabelExemptionRule.

Covers the `ser-label-exemption-rule` spec's "Electric label is exempt in
Madrid", "Non-electric label is not exempt in Madrid", "Electric label is
exempt in unconfigured cities", and "Non-electric label is not exempt in
unconfigured cities" scenarios.
"""

import pytest

from mobility_manager.domain.value_objects.ambient_label import AmbientLabel
from mobility_manager.infrastructure.parking_services.ser_label_exemption_rules import (
    CitySerLabelExemptionRule,
)

_NON_ELECTRIC_LABELS = [AmbientLabel.A, AmbientLabel.B, AmbientLabel.C, AmbientLabel.ECO]


def test_madrid_electric_label_is_exempt() -> None:
    rule = CitySerLabelExemptionRule()

    assert rule.is_label_exempt("madrid", AmbientLabel.ZERO) is True


@pytest.mark.parametrize("label", _NON_ELECTRIC_LABELS)
def test_madrid_non_electric_label_is_not_exempt(label: AmbientLabel) -> None:
    rule = CitySerLabelExemptionRule()

    assert rule.is_label_exempt("madrid", label) is False


def test_unconfigured_city_electric_label_is_exempt() -> None:
    rule = CitySerLabelExemptionRule()

    assert rule.is_label_exempt("barcelona", AmbientLabel.ZERO) is True


@pytest.mark.parametrize("label", _NON_ELECTRIC_LABELS)
def test_unconfigured_city_non_electric_label_is_not_exempt(label: AmbientLabel) -> None:
    rule = CitySerLabelExemptionRule()

    assert rule.is_label_exempt("barcelona", label) is False
