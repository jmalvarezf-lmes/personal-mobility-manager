## ADDED Requirements

### Requirement: SerExemptionZoneRule port and city-dispatching implementation
The system SHALL define a `SerExemptionZoneRule` abstract port with `is_zone_eligible(zone: SerZone) -> bool`, deciding whether a given zone qualifies for SER exemption eligibility at all, independent of whether any vehicle actually has a stored exemption. The system SHALL provide a single hardcoded implementation, `CitySerExemptionZoneRule`, that dispatches by `zone.city_code`: for `city_code == "madrid"`, it SHALL return `True` only if `zone.zone_type == "Verde"`; for any other `city_code` (including unknown/future cities), it SHALL return `True` unconditionally. This implementation SHALL perform no I/O (no database, no network) — the rule is a fixed, hardcoded fact per city.

#### Scenario: Madrid green zone is eligible
- **WHEN** `CitySerExemptionZoneRule.is_zone_eligible(zone)` is called with a zone whose `city_code` is `"madrid"` and `zone_type` is `"Verde"`
- **THEN** it returns `True`

#### Scenario: Madrid non-green zone is not eligible
- **WHEN** `CitySerExemptionZoneRule.is_zone_eligible(zone)` is called with a zone whose `city_code` is `"madrid"` and `zone_type` is not `"Verde"` (e.g. `"Azul"`)
- **THEN** it returns `False`

#### Scenario: Non-Madrid cities are always eligible
- **WHEN** `CitySerExemptionZoneRule.is_zone_eligible(zone)` is called with a zone whose `city_code` is anything other than `"madrid"`
- **THEN** it returns `True`, regardless of `zone_type`
