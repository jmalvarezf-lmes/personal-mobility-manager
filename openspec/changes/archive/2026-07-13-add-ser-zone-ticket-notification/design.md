## Context

`SerTicketTriggerHandler` was scaffolded as an inert no-op subscriber to `VehicleLocationUpdated` in `add-vehicle-location-notification`, specifically so this behavior could be widened later without touching event-publisher wiring. `NotificationDispatchHandler`, the sibling subscriber to the same event, already implements the "did this vehicle meaningfully move" check (previous-location lookup, `distance_m`, `NOTIFICATION_MOVEMENT_THRESHOLD_METERS` threshold) and the "look up owner, render localized template, call `SendNotification`" pipeline. `FindContainingSerZone` already exists and correctly uses only precise `ser_zones` geometry (never the `ser_zone_areas` frontier geometry — that constraint was set explicitly in `add-ser-zone-frontiers` and must hold here too, since this is now a real containment/ticket-liability consumer, not just a map query).

What's missing is the piece that decides, given "the vehicle is inside zone X," whether a ticket is actually required. That decision is known in advance to be temporary in its simplest form — it will need to weigh proximity to the owner's home address (residents are often exempt near home), a resident permit held for that specific zone, and the zone's enforcement hours/timetable (SER zones aren't ticketable 24/7). None of that data exists in the domain yet. Rather than embed a bare `zone is not None` check inline in the handler (which would need to be torn out and replaced later), this change introduces the decision as its own use case now, sized to receive those factors one at a time as injected dependencies.

## Goals / Non-Goals

**Goals:**
- Activate `SerTicketTriggerHandler` to notify a vehicle owner when their vehicle's location is inside a SER zone and a ticket is currently required.
- Reuse the existing movement-threshold check exactly as `NotificationDispatchHandler` implements it, rather than inventing a second, different "did it move" comparison.
- Introduce `DetermineSerTicketRequirement` as a standalone, dependency-injectable use case — the single seam later changes extend (home proximity, resident permits, enforcement hours) without touching `SerTicketTriggerHandler` or any other caller.
- Reuse `FindContainingSerZone`, `SendNotification`, `VehicleLocationRepository.get_previous`, and the notification-template mechanism as-is.

**Non-Goals:**
- Automatic ticket creation. This change only sends a notification telling the owner a ticket must be created; no `SerTicketProvider` is invoked.
- Any enforcement-hours/timetable modeling. The notification fires regardless of time of day in this change — an accepted, explicit limitation, not an oversight.
- Any home-proximity or resident-permit logic. `DetermineSerTicketRequirement` is a pure presence check in this change; those factors are deferred to future changes that will inject new dependencies into it.
- Deduplication beyond the existing movement threshold. A vehicle that moves past the threshold multiple times while remaining inside the same SER zone will be notified each time — this mirrors the existing movement-notification behavior exactly (no additional "already notified for this zone" state is introduced) and any zone-entry-specific debounce is left for a later change if it proves necessary in practice.

## Decisions

**Reuse the movement-threshold check verbatim, not a zone-transition comparison.** An earlier design draft compared the *previous* zone containment to the *current* one (notify only on `None → Zone` or `ZoneA → ZoneB` transitions). The chosen approach instead reuses the exact same "distance since previous location vs. `NOTIFICATION_MOVEMENT_THRESHOLD_METERS`" check `NotificationDispatchHandler` already performs: if the location is unchanged (below threshold), skip; otherwise, check zone containment fresh. This is simpler, needs no new state, and matches the mental model of "the same logic that decides whether we notify about movement also decides whether it's worth re-checking the zone."
- *Alternative considered*: zone-to-zone transition comparison (an explicit `previous_zone != current_zone` check via a second `FindContainingSerZone` call on the previous coordinates). Rejected as unnecessary complexity — it requires an extra zone lookup per event and its own edge cases (e.g. boundary flapping) for a case the simpler threshold reuse already handles well enough.

**`DetermineSerTicketRequirement` is a use case, not a domain entity method or a bare function.** Even though its current logic is a one-line presence check, it's modeled as a full use case (constructor-injectable, own module, own tests) because every anticipated future factor (home proximity, resident permit, enforcement hours) requires collaborators `SerZone` itself doesn't and shouldn't own (a home-location value, a resident-permits repository, a clock/schedule source). Building it as a use case now avoids a later refactor from "free function" to "class with dependencies" — the seam is sized correctly from the start.
- *Alternative considered*: a method on `SerZone` (`zone.requires_ticket_for(location)`). Rejected because `SerZone` is a pure spatial domain entity with no repository access; giving it responsibility for a decision that will need repository-backed data (home address, permits) would violate the entity's current boundaries.
- *Alternative considered*: inline logic directly in `SerTicketTriggerHandler`. Rejected per the proposal's explicit ask — the whole point is a scaffold that widens without touching the handler or any other caller.

**No new domain event.** `SerTicketTriggerHandler` already subscribes to `VehicleLocationUpdated`; this change fills in its body rather than introducing a new event type (e.g. `VehicleEnteredSerZone`) that the handler would react to indirectly. A new event was considered during exploration but rejected once the existing scaffold surfaced — it already provides the exact seam needed, without an extra layer of indirection.

**Template content includes both plate and zone number.** Consistent with `NotificationDispatchHandler`'s existing "vehicle moved" message (which includes the plate), the new template includes the zone number so the owner knows which zone the notification refers to, following the existing `render(key, language, **kwargs)` mechanism with no changes to that mechanism's signature.

## Risks / Trade-offs

- **[Risk] Re-notification while parked, past the movement threshold.** Since this reuses the plain movement threshold (not a zone-transition check), a vehicle that shifts position by more than the threshold multiple times while remaining inside the same SER zone (e.g., repositioned within a long parking strip) will receive multiple "ticket required" notifications. → **Mitigation**: accepted for this change, consistent with how the existing movement notification already behaves; revisit only if it proves noisy in practice, since adding transition-state tracking is straightforward to layer on later without touching `DetermineSerTicketRequirement`.
- **[Risk] No enforcement-hours awareness means false-positive notifications outside ticketable hours.** → **Mitigation**: explicitly accepted scope limitation per this change's proposal; `DetermineSerTicketRequirement`'s seam is where this gets added once zone schedule data exists.
- **[Risk] `DetermineSerTicketRequirement` being "just a presence check" today might tempt a future implementer to inline-optimize it away.** → **Mitigation**: the requirement `ser-ticket-requirement` spec and this design doc both record why the seam exists; the use case's docstring should carry the same rationale.

## Migration Plan

No data migration. No new environment variables. `SerTicketTriggerHandler` is already registered in `app.py`; only its handler body and its constructor's injected dependencies change (needs `VehicleLocationRepository`, `VehicleRepository`, `FindContainingSerZone`, `DetermineSerTicketRequirement`, `UserPreferences`/`SendNotification` collaborators — mirroring what `NotificationDispatchHandler` already receives). Rollback is a plain revert; nothing external depends on this handler's active behavior yet.

## Open Questions

None outstanding — movement-threshold reuse, first-location handling, enforcement-hours scope, and the use-case-vs-function shape for `DetermineSerTicketRequirement` were all resolved during exploration.
