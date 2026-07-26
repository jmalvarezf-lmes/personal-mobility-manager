## ADDED Requirements

### Requirement: SerLabelExemptionRule port and city-dispatching implementation
The system SHALL define a `SerLabelExemptionRule` abstract port with `is_label_exempt(city_code: str, label: AmbientLabel) -> bool`, deciding whether a given DGT ambient label is SER-exempt in a given city, independent of any vehicle's stored manual exemption or the zone's own eligibility. The system SHALL provide a single hardcoded implementation, `CitySerLabelExemptionRule`, that dispatches by `city_code`: for every `city_code`, including `"madrid"` and any other (unknown/future) city, it SHALL return `True` if and only if `label == AmbientLabel.ZERO`. This implementation SHALL perform no I/O (no database, no network) — the rule is a fixed, hardcoded fact per city, with unconfigured cities defaulting to the same electric-exempt behavior as configured ones.

#### Scenario: Electric label is exempt in Madrid
- **WHEN** `CitySerLabelExemptionRule.is_label_exempt(city_code, label)` is called with `city_code == "madrid"` and `label == AmbientLabel.ZERO`
- **THEN** it returns `True`

#### Scenario: Non-electric label is not exempt in Madrid
- **WHEN** `CitySerLabelExemptionRule.is_label_exempt(city_code, label)` is called with `city_code == "madrid"` and `label` in `{A, B, C, ECO}`
- **THEN** it returns `False`

#### Scenario: Electric label is exempt in unconfigured cities
- **WHEN** `CitySerLabelExemptionRule.is_label_exempt(city_code, label)` is called with a `city_code` other than `"madrid"` and `label == AmbientLabel.ZERO`
- **THEN** it returns `True`

#### Scenario: Non-electric label is not exempt in unconfigured cities
- **WHEN** `CitySerLabelExemptionRule.is_label_exempt(city_code, label)` is called with a `city_code` other than `"madrid"` and `label` in `{A, B, C, ECO}`
- **THEN** it returns `False`
