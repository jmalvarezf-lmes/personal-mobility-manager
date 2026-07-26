## Why

Vehicles with DGT ambient label `0` (fully electric) are entitled to free parking and do not need a SER ticket, but `DetermineSerTicketRequirement` has no way to know a vehicle's ambient label today — it only considers enforcement hours, active tickets, and stored manual exemptions. Electric-vehicle owners are currently being issued SER tickets (and, per `ser-ticket-auto-creation`, real paid tickets via the auto-creation flow) that they should never receive.

## What Changes

- Add a new `SerLabelExemptionRule` port with `is_label_exempt(city_code: str, label: AmbientLabel) -> bool`, mirroring the existing `SerExemptionZoneRule` per-city dispatch pattern.
- Add `CitySerLabelExemptionRule`, a single hardcoded, pure (no I/O) dispatcher implementation: for `city_code == "madrid"`, exempt only when `label == AmbientLabel.ZERO`; for any other (including unknown/future) `city_code`, exempt unconditionally for `label == AmbientLabel.ZERO` — unconfigured cities default to exempt, matching `CitySerExemptionZoneRule`'s permissive precedent for unconfigured cities.
- `DetermineSerTicketRequirement` gains two new injected constructor dependencies: `VehicleAmbientLabelRepository` (already defined by the `ambient-label` capability, already wired in `app.py`) and the new `SerLabelExemptionRule`.
- `execute()` gains a new short-circuit: once zone/enforcement/active-ticket checks pass, look up the vehicle's `VehicleAmbientLabel`. If its `status == AmbientLabelStatus.FOUND` and `label_exemption_rule.is_label_exempt(zone.city_code, label)` returns `True`, return `False` (no ticket required) — without consulting the manual-exemption repository or `SerExemptionZoneRule` at all, since the two exemption paths (electric label vs. stored manual exemption) are independent OR conditions.
- Any other ambient-label state — no row (`None`), `NOT_FOUND`, or `ERROR` — falls through unchanged to the existing manual-exemption check. This is a deliberate fail-safe: an unresolved lookup must never be treated as proof of an electric label, since that risks silently skipping a ticket the vehicle actually owes.
- Wire the new dependency in `app.py`: construct one `CitySerLabelExemptionRule()` instance and pass it plus the already-existing `vehicle_ambient_label_repo` into `DetermineSerTicketRequirement`.

## Capabilities

### New Capabilities
- `ser-label-exemption-rule`: `SerLabelExemptionRule` port and `CitySerLabelExemptionRule` per-city dispatching implementation deciding whether a given ambient label is SER-exempt in a given city.

### Modified Capabilities
- `ser-ticket-requirement`: `DetermineSerTicketRequirement` gains the ambient-label exemption check described above, as a new independent short-circuit alongside the existing manual-exemption check.

## Impact

- `src/mobility_manager/domain/ports/ser_label_exemption_rule.py` (new port)
- `src/mobility_manager/infrastructure/parking_services/ser_label_exemption_rules.py` (new dispatcher, sibling of `ser_exemption_zone_rules.py`)
- `src/mobility_manager/application/use_cases/determine_ser_ticket_requirement.py` (two new constructor deps, new execute() branch)
- `src/mobility_manager/presentation/api/app.py` (wiring)
- Tests: unit tests for the new port's dispatcher, and updated unit tests for `DetermineSerTicketRequirement` covering the new short-circuit and each ambient-label status
