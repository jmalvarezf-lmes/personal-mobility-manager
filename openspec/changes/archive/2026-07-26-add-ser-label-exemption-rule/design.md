## Context

`DetermineSerTicketRequirement` (`ser-ticket-requirement` capability) currently decides ticket requirement from four things: zone presence, `SerEnforcementSchedule.is_active_now`, an active `ParkingTicket`, and a stored `VehicleSerParkingExemption` gated by the per-city `SerExemptionZoneRule` (`ser-exemption-zone-rule` capability, e.g. Madrid requires the zone to be `"Verde"`).

Separately, the `ambient-label` capability already resolves and persists each vehicle's DGT `AmbientLabel` (`A | B | C | ECO | 0`) via `VehicleAmbientLabelRepository`, with lookup outcome tracked by `AmbientLabelStatus` (`FOUND | NOT_FOUND | ERROR`). Label `0` (electric) is DGT-classified as exempt from paid parking, independent of any vehicle's manually stored `VehicleSerParkingExemption`. Nothing today connects the two.

## Goals / Non-Goals

**Goals:**
- Give `DetermineSerTicketRequirement` a second, independent path to "not required": the vehicle's ambient label is electric (`0`) and the label-exemption rule for the zone's city says that's exempt.
- Keep the per-city variance the manual-exemption path already has, via a sibling port (`SerLabelExemptionRule` / `CitySerLabelExemptionRule`) rather than a hardcoded universal check, in case a city is later found not to honor the national label-0 rule.
- Default unconfigured cities to exempt (permissive), matching `CitySerExemptionZoneRule`'s existing precedent of defaulting unconfigured cities to always-eligible.
- Treat anything other than a confirmed `FOUND` + `label == ZERO` as "not exempt" (fail-safe): a `None` row, `NOT_FOUND`, or `ERROR` must never be read as proof of an electric label.

**Non-Goals:**
- No change to the manual `VehicleSerParkingExemption` flow or `SerExemptionZoneRule` — the two exemption paths are independent ORs, not merged into one.
- No retry/backfill logic for vehicles whose label lookup hasn't resolved yet — that's owned entirely by `ambient-label`'s existing `AmbientLabelScheduler`.
- No UI/notification changes — this only affects the boolean `DetermineSerTicketRequirement.execute()` returns.

## Decisions

**1. New port mirrors `SerExemptionZoneRule`'s shape, not a new abstraction family.** `SerLabelExemptionRule.is_label_exempt(city_code: str, label: AmbientLabel) -> bool`, with `CitySerLabelExemptionRule` dispatching a `_CITY_RULES: dict[str, Callable[[AmbientLabel], bool]]` exactly like `ser_exemption_zone_rules.py`'s `_madrid_is_eligible` dispatch. Alternative considered: fold this into `SerExemptionZoneRule` itself (it already dispatches per city) — rejected, because that port's signature takes a `SerZone`, not a `(city_code, label)` pair, and the two facts (zone-type eligibility vs. label eligibility) are conceptually and temporally independent (one needs a matching stored exemption first, the other never does).

**2. `execute()` treats the label check as a second, unconditional-of-exemption OR branch**, not nested inside the existing exemption branch. After the existing zone/enforcement/active-ticket short-circuits, the new logic runs: fetch `VehicleAmbientLabel` via the (already app.py-wired) `VehicleAmbientLabelRepository`; if `status == FOUND and label_exemption_rule.is_label_exempt(zone.city_code, label)`, return `False` immediately, without consulting the manual-exemption repository or `SerExemptionZoneRule` at all. Otherwise, fall through to the existing manual-exemption logic unchanged. Alternative considered: only check the label if the manual-exemption path already returned "required" — rejected, since the two facts are unrelated and ordering by cheaper-check-first is simpler when the label check is a flat early branch rather than conditional on the other branch's outcome.

**3. Fail-safe default for unresolved label status.** Only `AmbientLabelStatus.FOUND` with `label == AmbientLabel.ZERO` counts. `None` (never looked up), `NOT_FOUND`, and `ERROR` all fall through as "not exempt via label." This is a different axis from Decision 4's permissive city default — it's about *certainty of the vehicle fact*, not about *city policy* — and resolves in the opposite direction (fail-safe, not permissive), because misclassifying an unknown label as electric risks silently skipping a ticket the vehicle actually owes, whereas an unconfigured city defaulting to exempt merely assumes a national rule that hasn't yet been contradicted.

**4. Unconfigured cities default to exempt.** `CitySerLabelExemptionRule.is_label_exempt(city_code, label)` returns `label == AmbientLabel.ZERO` for any `city_code` not in `_CITY_RULES` (including `"madrid"`, since Madrid's rule is the same check) — i.e., today there is exactly one behavior for every city, but the port exists so a future city-specific carve-out (e.g. a city that doesn't honor the national electric exemption) can override it without touching `DetermineSerTicketRequirement`. This mirrors `CitySerExemptionZoneRule`'s existing permissive-unless-overridden precedent.

## Risks / Trade-offs

- [Every city currently behaves identically (label `0` → exempt), so the new port has no observable behavioral difference from a flat `label == ZERO` check today] → Mitigation: the port still earns its keep as the designated seam for the one thing we already know varies by city in this domain (SER-style zone policy), consistent with `ser-exemption-zone-rule`'s precedent; no logic is duplicated to get this.
- [Two independent exemption paths (manual + label) increase the number of states to reason about in `DetermineSerTicketRequirement`] → Mitigation: keep them strictly independent ORs in both code and tests — never let one branch's outcome influence the other's evaluation.
- [`VehicleAmbientLabelRepository.get_by_vehicle_id` adds a DB round-trip to every `execute()` call that reaches this point] → Mitigation: it only runs after the zone/enforcement/active-ticket short-circuits, same cost tier as the existing exemption-repo lookup it sits alongside.

## Open Questions

None outstanding — scope (per-city port) and unconfigured-city default (permissive) were resolved in explore mode before this design was written.
