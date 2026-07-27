## 1. Domain: ParkingTicket gains zone fields

- [x] 1.1 Add `city_code: str | None` and `zone_number: str | None` fields to `ParkingTicket` (`src/mobility_manager/domain/entities/parking_ticket.py`).
- [x] 1.2 Update every existing `ParkingTicket(...)` construction site to pass the two new fields: `src/mobility_manager/infrastructure/repositories/postgres/parking_ticket_repo.py` (read path), `tests/application/test_determine_ser_ticket_requirement.py`, `tests/application/event_handlers/test_ser_ticket_creation_trigger_handler.py`, `tests/application/use_cases/test_create_ser_ticket.py`, `tests/infrastructure/test_parking_ticket_repo_integration.py`, `tests/presentation/test_parking_router.py`.

## 2. Database: persist the new zone fields

- [x] 2.1 Add nullable `city_code` (Text) and `zone_number` (Text) columns to `parking_tickets_table` in `src/mobility_manager/infrastructure/orm/tables.py`.
- [x] 2.2 Generate a new Alembic migration (`make db-revision msg="add_zone_to_parking_tickets"`) adding the two nullable columns; no backfill.
- [x] 2.3 Update `PostgresParkingTicketRepository.save` and `.find_active_for_vehicle` (`src/mobility_manager/infrastructure/repositories/postgres/parking_ticket_repo.py`) to write and read `city_code`/`zone_number`.
- [x] 2.4 Update/add integration tests in `tests/infrastructure/test_parking_ticket_repo_integration.py` covering: a ticket saved with zone fields round-trips correctly; a ticket saved with `None` zone fields (simulating a legacy row) round-trips as `None`.

## 3. Infrastructure: ElParking provider populates the zone fields

- [x] 3.1 In `ElParkingSerTicketProvider.create_ticket` (`src/mobility_manager/infrastructure/ser_ticket_providers/elparking/provider.py`), pass `ser_zone.city_code` and `ser_zone.zone_number` (the zone already resolved at line ~124, used for id_ser_town/id_ser_zone/id_ser_rate resolution) into the returned `ParkingTicket`.
- [x] 3.2 Update `tests/` coverage for the ElParking provider to assert the returned `ParkingTicket.city_code`/`zone_number` match the resolved `SerZone`.

## 4. Application: zone-aware active-ticket short-circuit

- [x] 4.1 In `DetermineSerTicketRequirement.execute` (`src/mobility_manager/application/use_cases/determine_ser_ticket_requirement.py`), after `find_active_for_vehicle` returns a ticket: return `False` immediately if the ticket's `(city_code, zone_number)` is `(None, None)`; return `False` immediately if it equals `(zone.city_code, zone.zone_number)`; otherwise do not return and fall through to the ambient-label check as if no active ticket existed.
- [x] 4.2 Update the use case's module and `execute` docstrings to describe the zone-aware short-circuit and the legacy-`None` fail-safe.
- [x] 4.3 Update `tests/application/test_determine_ser_ticket_requirement.py`: existing "active ticket short-circuits" test now needs the ticket's zone to match; add new tests for (a) active ticket for a different known zone falls through to the ambient-label/exemption chain, (b) active ticket with `(None, None)` zone still short-circuits unconditionally.

## 5. Config: GPS-noise floor accessor

- [x] 5.1 Add `get_ser_ticket_creation_zone_change_floor_meters()` to `src/mobility_manager/config.py`, reading `SER_TICKET_CREATION_ZONE_CHANGE_FLOOR_METERS` with a default of `5`, following the exact int-with-fallback style of `get_ser_zone_containment_tolerance_cm()` (invalid/unset value falls back to `5`).
- [x] 5.2 Add unit tests in `tests/test_config.py` covering: default value when unset, valid override, invalid value falls back to default.

## 6. Handler: replace distance gate with zone-transition gate

- [x] 6.1 In `SerTicketCreationTriggerHandler.handle` (`src/mobility_manager/application/event_handlers/ser_ticket_creation_trigger_handler.py`), remove the existing effective-threshold movement gate (the `resolve_effective_threshold` / `notification_preferences_repo` lookup used only for that gate) and replace it with: if `previous` is not `None`, compute `distance`; if `distance < get_ser_ticket_creation_zone_change_floor_meters()`, skip silently (no zone lookups).
- [x] 6.2 When the distance clears the floor (or there is no previous location), resolve the previous location's SER zone via `FindContainingSerZone.execute` (skip this lookup when there is no previous location — treat previous zone as `None`) and the event's SER zone via the same use case.
- [x] 6.3 Compare `(zone.city_code, zone.zone_number)` for both (with `None` as its own state); if equal, skip silently before calling `DetermineSerTicketRequirement`.
- [x] 6.4 If different (including a vehicle's first-ever location, which always has previous zone `None` and thus always counts as "different"), proceed exactly as today: call `DetermineSerTicketRequirement.execute(zone, event.vehicle_id, at=event.received_at)` and continue to ticket creation if required.
- [x] 6.5 Drop the now-unused `notification_preferences_repo` constructor dependency and `_TYPE_KEY` constant from the handler if nothing else in the file uses them; update its wiring in `src/mobility_manager/presentation/api/factories.py` (or wherever the handler is constructed) accordingly.
- [x] 6.6 Update the handler's module docstring and `handle`'s docstring to describe the new zone-transition + noise-floor gate instead of the movement-threshold gate.

## 7. Tests: creation trigger handler

- [x] 7.1 Update `tests/application/event_handlers/test_ser_ticket_creation_trigger_handler.py`: replace/remove tests asserting the old distance-threshold-skip behavior with tests for: (a) distance below the noise floor skips both zone lookups and creation, (b) distance above the floor but same zone skips creation without calling `DetermineSerTicketRequirement`, (c) zone changed (including into/out of "no zone") proceeds to `DetermineSerTicketRequirement`, (d) first-ever location (no previous) always proceeds regardless of zone, (e) zone changed away from an existing ticket's (different) zone still creates a new ticket.
- [x] 7.2 Verify existing scenarios unaffected by this change still pass unmodified: auto_create_ticket disabled, ticket not required, matching exemption, vehicle not found, provider failure → `SerTicketCreationFailed`.
- [x] 7.3 Check `tests/application/event_handlers/test_ser_ticket_creation_trigger_handler_observability.py` for any assumptions tied to the removed threshold gate or removed constructor dependency; update if needed.

## 8. Verification

- [x] 8.1 Run `make test` and confirm all non-integration tests pass.
- [x] 8.2 Run `make coverage` and confirm `domain/` stays at 100% and `application/` stays at or above 80%.

## 9. Fixes from 4R review

A post-implementation 4R review (readability, reliability, resilience, risk) found two CRITICAL issues, two WARNINGs, and one SUGGESTION. This section fixes findings 1, 2, 4, and 5; finding 3 (the SER zone repository's uncached full-table scan) is accepted as-is — no easy fix without introducing a cache, out of scope for this change.

- [x] 9.1 **(Fix #1, CRITICAL — duplicate ticket via wrong-zone active-ticket match)** Change `ParkingTicketRepository.find_active_for_vehicle(vehicle_id, at) -> ParkingTicket | None` (`src/mobility_manager/domain/ports/parking_ticket_repository.py`) to `find_all_active_for_vehicle(vehicle_id, at) -> list[ParkingTicket]`, returning every one of the vehicle's `ParkingTicket` rows whose `end_date > at` (not just the single row with the latest `end_date`). Update its docstring to drop the now-false "regardless of which zone" framing and state the new, narrower contract: callers that care about zone must inspect each returned ticket's own `(city_code, zone_number)`.
- [x] 9.2 Update `PostgresParkingTicketRepository` (`src/mobility_manager/infrastructure/repositories/postgres/parking_ticket_repo.py`) to implement `find_all_active_for_vehicle`: drop `.limit(1)`, use `.fetchall()`, map every row to a `ParkingTicket`, return `[]` when there are none (never `None`).
- [x] 9.3 In `DetermineSerTicketRequirement.execute` (`src/mobility_manager/application/use_cases/determine_ser_ticket_requirement.py`), replace the single-ticket lookup with: fetch `active_tickets = self._ticket_repo.find_all_active_for_vehicle(vehicle_id, at)`; short-circuit to `False` if *any* ticket in that list has `(city_code, zone_number) == (None, None)` (legacy fail-safe) or matches `(zone.city_code, zone.zone_number)` (already covered); otherwise fall through to the ambient-label/exemption chain exactly as if the vehicle had no active tickets. Update the module and `execute` docstrings to describe checking "any of the vehicle's active tickets," not "the" single one, and explain why a single most-recent-by-`end_date` ticket was not a safe proxy once a vehicle can hold concurrently-active tickets for different zones.
- [x] 9.4 Update `tests/application/test_determine_ser_ticket_requirement.py`: change `_FakeParkingTicketRepository` to return a list; update every existing call site; add tests for (a) two concurrent active tickets in different zones where only one matches the zone being checked (must still short-circuit via the matching one, not just the most-recent), (b) an empty list falls through, (c) a list containing a legacy `(None, None)` ticket short-circuits regardless of other tickets present.
- [x] 9.5 Update `tests/infrastructure/test_parking_ticket_repo_integration.py`: rename/rewrite `test_find_active_for_vehicle_returns_most_recent_end_date` (and the other `find_active_for_vehicle` tests) for the new `find_all_active_for_vehicle` list-returning method; add a case with two simultaneously-active tickets for the same vehicle in different zones, asserting both are returned.

- [x] 9.6 **(Fix #2, CRITICAL — design's frequency assumption doesn't hold for pushed locations)** Raise the GPS-noise floor default from 5 to 10 meters: change `get_ser_ticket_creation_zone_change_floor_meters()`'s fallback in `src/mobility_manager/config.py` from `"5"`/`5` to `"10"`/`10`, and update its docstring to note the 60/minute push endpoint (not just the 5-minute poll scheduler) as part of the rationale for the chosen value. Update `tests/test_config.py`'s default-value assertion accordingly.
- [x] 9.7 Add a second, per-vehicle rate limit to `POST /vehicles/{token}/location` (`src/mobility_manager/presentation/api/routers/vehicles.py`, `push_vehicle_location`): keep the existing `@limiter.limit("60/minute")` (per-remote-address, unchanged, guards against abuse across many tokens from one source) and stack a new `@limiter.limit("1/minute", key_func=<per-token key func>)` where the key func returns `request.path_params["token"]` — so a single vehicle (identified by its token in the URL) cannot push more than once a minute, capping how fast repeated zone-transition attempts can be triggered via this path regardless of GPS jitter frequency. Add/update a test in the presentation test suite covering the new per-token limit (a second push for the same token within the minute is rejected with 429; a push for a *different* token in the same window is not affected).
- [x] 9.8 Update `openspec/specs/vehicle-location-push/spec.md`'s "Push endpoint rate-limited" requirement (via this change's own delta spec, see below) to describe both limits.

- [x] 9.9 **(Fix #4, WARNING — stale port docstring)** Covered by 9.1's docstring update to `find_all_active_for_vehicle` — confirm no other stale "regardless of which zone" language remains anywhere in `parking_ticket_repository.py`.
- [x] 9.10 **(Fix #5, SUGGESTION — undocumented entity fields)** Add a short docstring note to `ParkingTicket` (`src/mobility_manager/domain/entities/parking_ticket.py`) explaining `city_code`/`zone_number`: identifies the SER zone the ticket was created for; `None` only for tickets persisted before these fields existed (their original zone can't be recovered), matching the convention already used by `SerZone`/`VehicleSerParkingExemption` for their own `(city_code, zone_number)` identity fields.

- [x] 9.11 Update `design.md` (D2, D5, Risks/Trade-offs) and the `ser-ticket-requirement`/`ser-ticket-auto-creation` delta specs to reflect the corrected list-based active-ticket check and the raised 10m floor default.
- [x] 9.12 Run `make test` and `make coverage` again; confirm `domain/`/`application/` targets still hold and the full suite (including the new push-rate-limit test) is green.
