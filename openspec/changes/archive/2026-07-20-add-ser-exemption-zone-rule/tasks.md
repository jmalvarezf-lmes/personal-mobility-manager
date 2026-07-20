## 1. Domain port

- [x] 1.1 Add `SerExemptionZoneRule` ABC in `src/mobility_manager/domain/ports/ser_exemption_zone_rule.py` with `is_zone_eligible(zone: SerZone) -> bool`

## 2. Infrastructure implementation

- [x] 2.1 Add `CitySerExemptionZoneRule` in `src/mobility_manager/infrastructure/parking_services/ser_exemption_zone_rules.py`: dict-dispatch by `zone.city_code`, with a `"madrid"` entry checking `zone.zone_type == MadridZoneType.Verde.display_name` and a default returning `True` for any other city
- [x] 2.2 Unit tests for `CitySerExemptionZoneRule`: Madrid green zone eligible, Madrid non-green zone not eligible, non-Madrid city always eligible

## 3. Use case change

- [x] 3.1 Add `exemption_zone_rule: SerExemptionZoneRule` constructor parameter to `DetermineSerTicketRequirement`
- [x] 3.2 Update `execute()`'s final step: only return `False` when the exemption matches AND `exemption_zone_rule.is_zone_eligible(zone)` is `True`; otherwise return `True`
- [x] 3.3 Update module docstring to describe the new dependency and updated decision logic

## 4. Wiring

- [x] 4.1 Instantiate `CitySerExemptionZoneRule()` in `app.py` and pass it into `DetermineSerTicketRequirement`'s construction alongside `ser_enforcement_schedule` and `exemption_repo`

## 5. Test fallout

- [x] 5.1 Update `test_execute_returns_false_when_vehicle_has_matching_exemption` in `tests/application/test_determine_ser_ticket_requirement.py` to use a `"Verde"` zone (still exempt)
- [x] 5.2 Add a test asserting a matching exemption in a non-green (`"Azul"`) Madrid zone now returns `True` (ticket required)
- [x] 5.3 Add/update a fake `SerExemptionZoneRule` test double and wire it into all existing `DetermineSerTicketRequirement` test construction calls
- [x] 5.4 Add a test asserting `is_zone_eligible` is not consulted when there is no matching exemption (short-circuit ordering)

## 6. Verification

- [x] 6.1 Run the full test suite and confirm no other callers of `DetermineSerTicketRequirement` broke (check `app.py` wiring and any integration tests)
