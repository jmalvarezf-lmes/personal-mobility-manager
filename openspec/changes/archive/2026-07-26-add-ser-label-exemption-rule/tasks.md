## 1. SerLabelExemptionRule port

- [x] 1.1 Create `src/mobility_manager/domain/ports/ser_label_exemption_rule.py`: abstract `SerLabelExemptionRule` port with `is_label_exempt(city_code: str, label: AmbientLabel) -> bool`, mirroring `ser_exemption_zone_rule.py`'s docstring style.

## 2. CitySerLabelExemptionRule implementation

- [x] 2.1 Create `src/mobility_manager/infrastructure/parking_services/ser_label_exemption_rules.py`: `CitySerLabelExemptionRule(SerLabelExemptionRule)` implementing `is_label_exempt` as `label == AmbientLabel.ZERO`, unconditional on `city_code` (every city, configured or not, currently shares the same rule — see design.md Decision 4), pure/no I/O.
- [x] 2.2 Add `tests/infrastructure/parking_services/test_ser_label_exemption_rules.py` covering: Madrid + electric label → `True`; Madrid + non-electric label (`A`, `B`, `C`, `ECO`) → `False`; an unconfigured city + electric label → `True`; an unconfigured city + non-electric label → `False`.

## 3. DetermineSerTicketRequirement changes

- [x] 3.1 Add `ambient_label_repo: VehicleAmbientLabelRepository` and `label_exemption_rule: SerLabelExemptionRule` constructor parameters to `DetermineSerTicketRequirement` (`src/mobility_manager/application/use_cases/determine_ser_ticket_requirement.py`).
- [x] 3.2 In `execute()`, after the existing active-ticket short-circuit and before the manual-exemption lookup, add the label-exemption branch: look up `ambient_label_repo.get_by_vehicle_id(vehicle_id)`; if the result's `status == AmbientLabelStatus.FOUND` and `label_exemption_rule.is_label_exempt(zone.city_code, label)` is `True`, return `False` immediately. Otherwise (no row, `NOT_FOUND`, or `ERROR`, or the rule returns `False`), fall through unchanged to the existing manual-exemption logic.
- [x] 3.3 Update the module/class docstrings in `determine_ser_ticket_requirement.py` to describe the new independent label-exemption branch and its fail-safe handling of unresolved ambient-label state (see design.md Decision 3).
- [x] 3.4 Update `tests/application/test_determine_ser_ticket_requirement.py`: add cases for (a) electric label + exempt city → ticket not required, without consulting the manual-exemption repo or zone rule; (b) non-electric label → falls through to existing manual-exemption behavior; (c) each of `None` row, `NOT_FOUND`, and `ERROR` status → falls through to existing manual-exemption behavior (no false-exempt).

## 4. Wiring

- [x] 4.1 In `src/mobility_manager/presentation/api/app.py`, construct a `CitySerLabelExemptionRule()` instance and pass it plus the already-existing `vehicle_ambient_label_repo` into the `DetermineSerTicketRequirement(...)` constructor call.

## 5. Verification

- [x] 5.1 Run `make test` and `make coverage`; confirm `domain/` stays at 100% and `application/` stays at/above 80%.
- [x] 5.2 Manually verify: an electric-labelled vehicle (once its ambient-label lookup has resolved to `0`) parked in an active SER zone does not get a ticket auto-created or a SER notification.
