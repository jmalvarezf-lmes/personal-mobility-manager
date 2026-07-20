## Why

Today a vehicle's SER parking exemption applies whenever it matches the current zone's `(city_code, zone_number)`, regardless of that zone's type. Madrid's actual exemption rule is narrower: the vehicle must be parked in a **green ("Verde") zone** to avoid paying, even if the `(city_code, zone_number)` matches. Other cities may have their own eligibility rules (or none). `DetermineSerTicketRequirement` must stay city-agnostic — it should not hardcode Madrid or any other city's rule — while still letting each city define what "eligible for exemption" means.

## What Changes

- Add a `SerExemptionZoneRule` port (`is_zone_eligible(zone: SerZone) -> bool`) that `DetermineSerTicketRequirement` consults, as a third injected constructor dependency, only after confirming the vehicle's stored exemption already matches the zone's `(city_code, zone_number)`.
- Add a single hardcoded implementation (`CitySerExemptionZoneRule`) that dispatches per `zone.city_code`: for `"madrid"`, a zone is only eligible if `zone.zone_type == "Verde"`; any other/unknown city defaults to always-eligible (today's behavior, unchanged).
- **BREAKING** (behavioral, not API): a Madrid vehicle whose stored exemption matches its current zone but whose zone is not green will now be told a ticket is required, where previously it was not.
- Wire the new rule into `app.py` alongside `ser_enforcement_schedule` and `exemption_repo`.

## Capabilities

### New Capabilities
- `ser-exemption-zone-rule`: a city-keyed port deciding whether a given `SerZone` qualifies for exemption eligibility at all, with Madrid's green-zone-only rule as the sole current implementation and an always-eligible default for other cities.

### Modified Capabilities
- `ser-ticket-requirement`: `DetermineSerTicketRequirement` gains a third injected `SerExemptionZoneRule` dependency; a matching `(city_code, zone_number)` exemption is no longer sufficient by itself — the zone must also pass the injected rule's `is_zone_eligible(zone)` check.

## Impact

- `src/mobility_manager/application/use_cases/determine_ser_ticket_requirement.py`: new constructor parameter and final-step logic change.
- `src/mobility_manager/domain/ports/` (new file): `SerExemptionZoneRule` ABC.
- `src/mobility_manager/infrastructure/parking_services/` (new file): `CitySerExemptionZoneRule` implementation.
- `src/mobility_manager/presentation/api/app.py`: wiring of the new dependency.
- `tests/application/test_determine_ser_ticket_requirement.py`: update the existing matching-exemption test (currently uses a non-green zone) and add green/non-green coverage.
- No database schema or API contract changes.
