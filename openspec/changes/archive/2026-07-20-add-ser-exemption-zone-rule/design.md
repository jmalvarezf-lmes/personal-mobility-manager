## Context

`DetermineSerTicketRequirement` (see `ser-ticket-requirement` spec) currently treats a matching `(city_code, zone_number)` exemption as sufficient on its own. Madrid's real rule is narrower: the vehicle must additionally be parked in a "Verde" (green) zone. `SerZone.zone_type` already carries this fact as a validated string (e.g. `"Azul"`, `"Verde"`); the raw `MadridZoneType` enum that owns the `"Verde"` literal lives in `infrastructure/parking_services/madrid/zone_type.py`, which the application layer must not import.

Two existing per-city precedents were considered and rejected as direct models:
- `SerEnforcementSchedule.is_active_now(city_code)`: single port/implementation, but per-city variance is *data* (DB tables for timetable/holidays). This rule has no configurable data — it's a fixed fact about Madrid — so a DB table would be pure ceremony.
- `zones.py`'s `_resolve_colour()`: inline `if city == "madrid": import MadridZoneType`. Fine in the presentation layer for a rendering concern, but importing `MadridZoneType` directly into an application-layer use case would violate the dependency direction Clean Architecture enforces here.

## Goals / Non-Goals

**Goals:**
- Keep `DetermineSerTicketRequirement` fully city-agnostic: it must not name Madrid or any zone-type string.
- Encapsulate Madrid's "must be green" fact in exactly one small, hardcoded, pure (no I/O) infrastructure class.
- Preserve today's behavior for every city other than Madrid, and for Madrid vehicles already in a green zone.
- Match the existing constructor-injection/testing style (`enforcement_schedule`, `exemption_repo` are both injected and faked in tests).

**Non-Goals:**
- No database table or per-deployment configurability for this rule (confirmed with the user: this almost never changes; hardcoding is fine).
- No change to the exemption storage model, the exemption CRUD endpoints, or the `(city_code, zone_number)` matching logic itself.
- No handling of cities beyond Madrid; other cities simply get the always-eligible default.

## Decisions

**A single injected `SerExemptionZoneRule` port, one dispatching implementation, not a registry-of-providers.**
`SerTicketProviderRegistry`/`BrandRegistry` build a `dict[str, Port]` because multiple *simultaneously enabled* implementations coexist and the caller picks one by an external key (provider/brand). Here there is always exactly one applicable rule per call (`zone.city_code`), so a single class that owns a `{city_code: predicate}` mapping internally and defaults to always-eligible is simpler and keeps the use case's call site to one line: `self._exemption_zone_rule.is_zone_eligible(zone)`. Adding a second city's rule later means adding one dict entry to this class — nothing else changes.

**Port shape:** `SerExemptionZoneRule.is_zone_eligible(zone: SerZone) -> bool`, in `domain/ports/ser_exemption_zone_rule.py`, following the existing ABC-per-file port convention (see `ser_enforcement_schedule.py`).

**Implementation location and name:** `CitySerExemptionZoneRule` in `infrastructure/parking_services/ser_exemption_zone_rules.py` (not under `infrastructure/parking_services/madrid/`, since the class itself is city-agnostic — it only happens to currently contain one Madrid-specific dict entry, which does import `MadridZoneType` for the `"Verde"` comparison, keeping that literal in exactly one place instead of being re-typed as a bare string).

**Check ordering in `DetermineSerTicketRequirement.execute`:** the `(city_code, zone_number)` match is checked first (as today), and `is_zone_eligible` is only consulted once a match is confirmed. This preserves the "cheapest/already-necessary check first" ordering already documented in the use case's docstring, and avoids invoking the zone-rule dependency at all when there's no exemption to evaluate in the first place (mirrors the existing enforcement-schedule short-circuit before the exemption repo).

**Dependency direction:** `CitySerExemptionZoneRule` (infrastructure) implements a port defined in `domain/ports`; `DetermineSerTicketRequirement` (application) depends only on the port, injected via constructor, wired once in `app.py` next to `ser_enforcement_schedule` and `exemption_repo`.

## Risks / Trade-offs

- **[Behavior change for existing Madrid users]** A vehicle with a stored exemption for a now-non-green zone will start being told a ticket is required, where it previously wasn't. → This is the explicit intent of the change (matches Madrid's actual rule); no migration needed since exemption *storage* is untouched, only the real-time ticket-requirement check.
- **[Hardcoded rule needs a code change + deploy to update]** Accepted per Goals — this fact almost never changes, and a data-driven table was judged not worth the added ceremony for a single fixed rule.
- **[Existing test now asserts stale behavior]** `test_execute_returns_false_when_vehicle_has_matching_exemption` uses `zone_type="Azul"` and expects an exempt result — under the new rule this must change to `"Verde"` (still exempt) plus a new case asserting `"Azul"` now requires a ticket despite the matching exemption.

## Migration Plan

No data migration. Deploy is a single release of the application/infrastructure code plus the `app.py` wiring change; rollback is a plain revert (no schema or stored-data impact either direction).

## Open Questions

None outstanding — scope, hardcoding vs. data-driven, and the port-vs-registry shape were all resolved during exploration.
