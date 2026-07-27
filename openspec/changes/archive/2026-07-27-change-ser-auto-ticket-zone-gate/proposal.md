## Why

`SerTicketCreationTriggerHandler` currently gates on the same kind of check as the notification handler it shares `VehicleLocationUpdated` with: skip if the vehicle moved less than a configurable distance threshold since its previous recorded location. That gate makes sense for a "you should get a ticket" reminder, but it is the wrong trigger for automatic ticket creation: a vehicle driving around inside the same already-covered SER zone can cross the distance threshold repeatedly without ever leaving the zone, while a vehicle that crosses into a new zone with only a small movement (e.g. parking just across a zone boundary) can stay under the threshold and never get checked at all. Automatic ticket creation should react to *zone transitions*, not raw distance.

Additionally, `DetermineSerTicketRequirement`'s existing "does the vehicle already have a ticket" short-circuit (`ParkingTicketRepository.find_active_for_vehicle`) is vehicle-scoped, not zone-scoped — `ParkingTicket` has no stored zone at all today. That means a vehicle with a still-active ticket for zone A that transitions into zone B is currently treated as "no ticket needed," even though its existing ticket doesn't cover zone B. Without fixing this, the new zone-transition gate would correctly detect the transition into B but the requirement check would still (incorrectly) say no ticket is needed, so no ticket would ever be created for the new zone. This has to land in the same change for the zone-transition gate to actually work as intended.

## What Changes

- `SerTicketCreationTriggerHandler` replaces its distance-threshold gate with a zone-transition gate: it looks up the SER zone containing the vehicle's previous recorded location and the SER zone containing the event's coordinates, and only proceeds to `DetermineSerTicketRequirement` when those two zones differ (including the "no zone" state, and always proceeding on a vehicle's first-ever recorded location, which has no previous zone to compare against).
- A new small GPS-noise floor is introduced ahead of the zone comparison: if the distance since the previous recorded location is below a technical, non-user-facing threshold, the handler skips without doing either zone lookup, treating the fix as GPS jitter rather than real movement. This floor is read from a new environment variable with a default of 5 meters — it is intentionally not exposed as a user preference (unlike the notification handler's movement threshold).
- `ParkingTicket` gains `city_code` and `zone_number` fields (both `str | None`, populated for every newly created ticket; `None` only for legacy rows created before this change). The ElParking provider already resolves the containing `SerZone` before submitting a ticket, so no extra lookup is needed to populate them.
- `DetermineSerTicketRequirement`'s active-ticket short-circuit becomes zone-aware: if the vehicle's active ticket's `(city_code, zone_number)` matches the zone being checked, it still short-circuits to `False` (already covered). If it's for a *different* zone, the check no longer short-circuits and falls through to the existing ambient-label/exemption chain instead — a different zone means the existing ticket doesn't excuse a new one. A legacy ticket with `city_code`/`zone_number` both `None` (created before this change) is treated as covering any zone, preserving today's behavior for it, since its real zone can't be recovered.
- This shared use case also serves `SerTicketNotificationTriggerHandler` — as a side effect, the "you need a ticket" notification will now correctly fire again after a vehicle with an existing ticket drives into a different zone, which was previously (incorrectly) suppressed.
- The notification handler's own distance-threshold gate is unchanged.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `ser-ticket-auto-creation`: the "SerTicketCreationTriggerHandler creates a SER ticket when required and auto-creation is enabled" requirement's step 3 (movement-threshold gate) is replaced by a zone-transition gate preceded by a fixed GPS-noise floor; the "Movement below the effective threshold skips the zone check" scenario is replaced accordingly; a new scenario covers a zone change away from an existing ticket's zone still requiring creation.
- `ser-ticket-provider`: the "ParkingTicket entity represents a created SER ticket" requirement gains `city_code`/`zone_number` fields; the "ElParkingSerTicketProvider implements ticket creation against the ElParking API" requirement's step 7 is updated to populate them from the already-resolved zone.
- `ser-ticket-requirement`: the "DetermineSerTicketRequirement use case" requirement's active-ticket short-circuit becomes zone-aware instead of purely vehicle-scoped.

## Impact

- `src/mobility_manager/application/event_handlers/ser_ticket_creation_trigger_handler.py` — replace the distance-threshold check with a zone-lookup-based comparison plus a noise floor.
- `src/mobility_manager/config.py` — add a new env-var accessor for the GPS-noise floor (default `5` meters), following the existing pattern of `get_ser_zone_containment_tolerance_cm`.
- `src/mobility_manager/domain/entities/parking_ticket.py` — add `city_code`/`zone_number` fields.
- `src/mobility_manager/domain/ports/parking_ticket_repository.py`, `src/mobility_manager/infrastructure/repositories/postgres/parking_ticket_repo.py`, `src/mobility_manager/infrastructure/orm/tables.py`, a new Alembic migration — persist and read the new nullable columns.
- `src/mobility_manager/infrastructure/ser_ticket_providers/elparking/provider.py` — populate the new fields from the zone it already resolves.
- `src/mobility_manager/application/use_cases/determine_ser_ticket_requirement.py` — zone-aware active-ticket comparison.
- Test files for all of the above (entity, provider, repo integration, `DetermineSerTicketRequirement`, `SerTicketCreationTriggerHandler`).
- No API or user-facing preference changes; one new nullable-column database migration.
