## Context

`RecordVehicleLocation` (the shared entry point for both pull-polled and pushed GPS fixes) discards a location update outright — no persistence, no `VehicleLocationUpdated` publication — whenever its coordinates exactly match the last stored fix for that vehicle. With the default 5-minute pull poll, a stationary vehicle produces an unbroken run of exact-duplicate fixes, so after the first ping in a spot, the event pipeline goes silent for that vehicle until it genuinely moves.

Two handlers subscribed to `VehicleLocationUpdated` decide whether a SER ticket is or should be required: `SerTicketCreationTriggerHandler` (auto-creates one) and `SerTicketNotificationTriggerHandler` (notifies the owner one is needed). Both additionally skip their own work when movement since the previous location is below a threshold — a fixed technical floor for creation, a per-user configurable one for notification — and the creation handler further skips when the SER zone containing the new location is unchanged from the zone containing the previous one.

`DetermineSerTicketRequirement`'s answer is not purely a function of position: it also depends on the SER enforcement schedule (time-of-day/weekday/holiday) and on whether the vehicle's existing `ParkingTicket`(s) are still active. Both of those can flip a stationary vehicle from "not required" to "required" with zero movement — e.g. enforcement activating at a fixed hour, or an existing ticket expiring. Today, nothing re-asks the question when that happens, because the only thing that ever triggers a re-ask is a `VehicleLocationUpdated` event, and the discard above suppresses exactly the events a stationary vehicle would otherwise generate.

Separately, the two handlers' previous-location/distance/zone-comparison logic is close to identical, copy-pasted rather than shared, and about to need the same additional rule.

## Goals / Non-Goals

**Goals:**
- A stationary vehicle's SER-ticket requirement gets re-evaluated on the existing poll cadence, not only on movement.
- The "should I bother re-checking" decision (movement floor, zone-unchanged, and the new active-ticket override) lives in one place, used identically by both SER handlers.
- No change to `DetermineSerTicketRequirement` itself, to `CreateSerTicket`, or to any other `VehicleLocationUpdated` subscriber's observable behavior.

**Non-Goals:**
- No new scheduler or time-based job independent of location polling (rejected in favor of riding the existing poll — see Decisions).
- No change to the SER enforcement-schedule or ticket-expiry logic themselves.
- No change to per-vehicle location history/storage semantics beyond skipping one redundant row write.

## Decisions

### D1: Ride the existing poll cadence rather than add a dedicated recheck scheduler
Two shapes were considered: (A) keep the event-driven model, but stop suppressing unchanged-location events so the existing 5-minute poll doubles as a recheck clock; (B) add an independent time-based job that periodically re-evaluates parked vehicles regardless of location events.

(A) was chosen: it reuses infrastructure that already exists (the poller), requires no new "which vehicles are currently parked" query, and keeps a single trigger path (`VehicleLocationUpdated`) for all SER-related logic. (B) would decouple time-based re-evaluation from movement-based re-evaluation more cleanly, but at the cost of a new scheduler and duplicated iteration/eligibility logic that (A) gets for free from the poller that already exists.

### D2: `RecordVehicleLocation` stops discarding, but still avoids a duplicate DB row
The discard is split into two independent effects that were previously coupled: persistence and publication. Persistence still skips writing a row identical to the last stored one (no bloat, no change to `get_previous`/`get_latest`/history semantics). Publication no longer depends on that check — `VehicleLocationUpdated` is published every time, with a freshly-constructed `received_at`, so `at`-sensitive checks downstream (enforcement-schedule "is active now", ticket expiry) see the current time, not the time of the first ping in that spot.

This does mean `VehicleLocationUpdated` no longer strictly means "the location changed" — it now means "we heard from the vehicle." Every existing subscriber (`NotificationDispatchHandler`, and the two SER handlers prior to this change) already computes its own distance-vs-previous-location check independently, so an unchanged-coordinates event is a safe no-op for the ones that don't get the new gate. No event schema change is needed — consumers that care about "did it actually move" already re-derive that from `VehicleLocationRepository.get_previous`, exactly as before.

### D3: The gate's condition is keyed on "does the vehicle hold any active ticket," not "did it move enough"
The naive fix — OR a "no active ticket" condition onto just the distance-floor check — is insufficient: the creation handler's separate zone-unchanged skip is a second gate with the identical flaw (a stationary vehicle's zone never changes, so it would still be silently skipped downstream of the floor check). The correct framing treats "holds an active ticket" as the condition that makes the movement/zone optimizations valid at all:

```
has_active_ticket = ticket_repo.find_all_active_for_vehicle(vehicle_id, at=now) is non-empty

if has_active_ticket:
    # existing optimization, unchanged in spirit: only bother on genuine movement/zone-change
    if no previous location:          proceed
    elif distance < floor:             skip
    elif zone unchanged vs previous:   skip
    else:                              proceed
else:
    # nothing currently covers this vehicle — always re-evaluate
    proceed
```

When an active ticket exists, `DetermineSerTicketRequirement` would short-circuit to `False` for the same zone anyway (see `ser-ticket-requirement`), so the movement/zone skip in that branch remains a pure cost optimization, not a correctness-bearing check — unchanged from today's behavior. When no active ticket exists, that optimization no longer applies, because the state that could change purely with time (schedule activation, ticket expiry) is exactly the state this branch is meant to catch.

This costs one extra `ParkingTicketRepository.find_all_active_for_vehicle` call per poll per vehicle, on every ping (not just ones that would otherwise proceed) — needed to know which branch applies. This is an existing, indexed, already-used query pattern; the added load is one call per vehicle per poll interval (default 5 minutes), which is negligible at any realistic fleet size.

### D4: Extract `SerZoneRecheckGate` as a single shared collaborator, not a shared base class or free function
Both `SerTicketCreationTriggerHandler` and `SerTicketNotificationTriggerHandler` depend on the same repositories already (`VehicleLocationRepository`, `ParkingTicketRepository` — the notification handler gains a dependency on the latter via the gate — and `FindContainingSerZone`). A small injected collaborator (application-layer use case, following the existing `FindContainingSerZone`/`DetermineSerTicketRequirement` pattern) with one method:

```
SerZoneRecheckGate.evaluate(event, movement_floor_meters) -> SerZoneRecheckDecision
    # decision.should_check: bool
    # decision.zone: SerZone | None   (resolved current zone, populated when should_check is True)
```

replaces the duplicated previous-location/distance/zone-resolution block in both handlers. Each handler still supplies its own `movement_floor_meters` (the fixed technical floor for creation, the per-user configurable threshold for notification) — the two floors remain independent values, per the existing explicit design intent that they never share a call or value. The gate resolves and returns the current zone so callers don't redundantly call `FindContainingSerZone` again.

A shared base class or mixin was considered and rejected: the two handlers' post-gate behavior (create vs. notify) is unrelated, and a single-method collaborator is simpler to test in isolation and to inject than a partial base class.

### D5: Unify the zone-unchanged optimization across both handlers
Today only the creation handler compares previous-zone vs. current-zone as an extra skip; the notification handler does not. Since `SerZoneRecheckGate` now owns this logic for both callers, the notification handler gains the same zone-unchanged skip (gated behind "has an active ticket," per D3) that the creation handler already has. This was an explicit choice (not an incidental side effect): the same reasoning applies to both — an unchanged zone with an active ticket already covering it will not produce a new "ticket required" outcome either way, so skipping is safe for both callers, and keeping the two handlers' optimization level in sync avoids the exact kind of drift this change is meant to eliminate.

## Risks / Trade-offs

- **[Risk]** `VehicleLocationUpdated` now fires every poll cycle for every vehicle, even fully idle ones, increasing event-handler dispatch volume. → **Mitigation**: every existing subscriber already no-ops cheaply on a zero-distance comparison; the new gate's only added per-vehicle-per-poll cost is one indexed ticket-existence query.
- **[Risk]** Widening `SerZoneRecheckGate`'s scope to also gate the notification handler's zone-unchanged skip is a behavior change beyond the minimal bug fix. → **Mitigation**: explicitly decided (D5) rather than incidental; the underlying reasoning (an active ticket for an unchanged zone can't produce a new outcome) is identical for both handlers.
- **[Risk]** A vehicle with an active ticket whose `(city_code, zone_number)` is `(None, None)` (legacy row, per `ser-ticket-requirement`'s fail-safe) is treated by `find_all_active_for_vehicle` as "has an active ticket" — the gate's optimization branch applies to it exactly as it does to any other active ticket, consistent with `DetermineSerTicketRequirement`'s own fail-safe treatment of that state. → No mitigation needed; this preserves existing fail-safe behavior rather than changing it.
- **[Risk]** When a vehicle holds no active ticket, `SerZoneRecheckGate` always signals a recheck; if `CreateSerTicket.execute` then has the provider create (and charge) a real ticket but fails to persist the corresponding `ParkingTicket` row, no row exists to make the gate stop signalling "recheck" — without mitigation this would drive repeated real charges on every subsequent poll for a stationary vehicle. → **Mitigation** (post-implementation fix): `CreateSerTicket.execute` retries `ticket_repo.save(ticket)` up to `_TICKET_SAVE_MAX_ATTEMPTS` (3) times, `_TICKET_SAVE_RETRY_DELAY_SECONDS` (0.2s) apart, before raising `SerTicketPersistenceError`. This only closes the realistic transient-failure window (query timeout, deadlock, momentary connection blip); an extended DB outage still surfaces as `SerTicketPersistenceError` — deliberately not fully solved here, since an outage long enough to defeat 3 quick retries already breaks much more of this app than just this save.

## Migration Plan

Single-PR change, no data migration, no schema change, no feature flag: the new gate is wired in at the same time both handlers start using it. Rollback is a plain revert.

## Open Questions

None outstanding — direction and scope were settled during exploration.
