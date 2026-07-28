## 1. Migration

- [x] 1.1 Add alembic migration under `alembic/versions/` adding nullable columns `latitude DOUBLE PRECISION`, `longitude DOUBLE PRECISION`, `auto_created BOOLEAN` to `parking_tickets`, following the existing single-purpose migration convention (e.g. `w0x1y2z3a4b5_add_city_code_to_ser_zone_tables.py`). No backfill — existing rows keep `NULL` for all three.
- [x] 1.2 Update `parking_tickets_table` in `src/mobility_manager/infrastructure/orm/tables.py` to add the three new nullable columns, matching the migration.

## 2. Domain entity

- [x] 2.1 Add `latitude: float | None`, `longitude: float | None`, `auto_created: bool | None` fields to `ParkingTicket` (`src/mobility_manager/domain/entities/parking_ticket.py`); update its module docstring to document the same "None only for pre-existing rows" precedent already used for `city_code`/`zone_number`.

## 3. CreateSerTicket use case

- [x] 3.1 In `src/mobility_manager/application/use_cases/create_ser_ticket.py`, add an `auto_created: bool = False` parameter to `CreateSerTicket.execute(...)`. When constructing the `ParkingTicket` to persist, set `latitude`/`longitude` from `resolved_location` (`resolved_location.lat`/`resolved_location.lng`) and `auto_created` from the new parameter.
- [x] 3.2 Update `tests/application/use_cases/test_create_ser_ticket.py` (or equivalent): assert persisted `ParkingTicket.latitude`/`longitude` match the explicit or fallback-resolved location in both the explicit-location and fallback-to-latest-location scenarios; assert default `auto_created=False`; add a case passing `auto_created=True` and asserting it is persisted unchanged.

## 4. ParkingTicketRepository

- [x] 4.1 Add `list_by_vehicle(vehicle_id: UUID, limit: int, offset: int) -> tuple[list[ParkingTicket], bool]` to the `ParkingTicketRepository` port (`src/mobility_manager/domain/ports/parking_ticket_repository.py`), documented analogously to `VehicleLocationRepository.list_history` — returns every ticket for the vehicle regardless of `auto_created`.
- [x] 4.2 Implement it in `PostgresParkingTicketRepository` (`src/mobility_manager/infrastructure/repositories/postgres/parking_ticket_repo.py`): `SELECT` filtered by `vehicle_id` only (no `auto_created` filter), ordered by `created_at DESC`, `LIMIT limit + 1 OFFSET offset` to derive `has_more` (mirroring whatever pattern `PostgresVehicleLocationRepository.list_history` already uses — reuse the same technique, don't invent a new one).
- [x] 4.3 Update `save()` in the same repository to persist the new `latitude`, `longitude`, `auto_created` columns.
- [x] 4.4 Extend `tests/infrastructure/test_parking_ticket_repo_integration.py` with cases for `list_by_vehicle`: returns both auto-created and manually created tickets, newest-first ordering, pagination (`has_more` true/false), and out-of-range offset.

## 5. ListSerTickets use case

- [x] 5.1 Add `src/mobility_manager/application/use_cases/list_ser_tickets.py`: `ListSerTickets` with `execute(vehicle_id: UUID, limit: int, offset: int) -> tuple[list[ParkingTicket], bool]`, delegating directly to `ParkingTicketRepository.list_by_vehicle(vehicle_id, limit=limit, offset=offset)`.
- [x] 5.2 Add `tests/application/use_cases/test_list_ser_tickets.py` with a mocked repository, asserting the delegation call args match `vehicle_id`, `limit`, `offset`.

## 6. Vehicle-list has_ser_tickets

- [x] 6.1 Add an existence-check method to `ParkingTicketRepository` (e.g. `has_any_for_vehicle(vehicle_id: UUID) -> bool`) and implement it in `PostgresParkingTicketRepository` as an `EXISTS`/`SELECT 1 ... LIMIT 1` query filtered by `vehicle_id` only (no `auto_created` filter) — not a full row fetch.
- [x] 6.2 Wire this into whatever use case/query currently backs `GET /vehicles` (locate it via the `location` field's existing resolution) so each returned item also carries `has_ser_tickets`, computed via the new existence check per vehicle.
- [x] 6.3 Add `has_ser_tickets: bool` to the vehicle-list response schema in `src/mobility_manager/presentation/api/schemas.py`.
- [x] 6.4 Extend the existing `GET /vehicles` unit/e2e tests: vehicle with an auto ticket → `true`; vehicle with only manual tickets → `true`; vehicle with no tickets → `false`.

## 7. SerTicketCreationTriggerHandler wiring

- [x] 7.1 In `src/mobility_manager/application/event_handlers/ser_ticket_creation_trigger_handler.py`, update the `self._create_ser_ticket.execute(...)` call (around line 259) to pass `auto_created=True`.
- [x] 7.2 Update `tests/application/event_handlers/test_ser_ticket_creation_trigger_handler.py`: assert the `CreateSerTicket.execute` call includes `auto_created=True`.

## 8. GET /vehicles/{vehicle_id}/ser-tickets endpoint

- [x] 8.1 Add `SerTicketListItemResponse` and `SerTicketHistoryResponse` (`items`, `has_more`) Pydantic schemas to `schemas.py`: `id`, `latitude` (nullable), `longitude` (nullable), `start_date` (from `created_at`), `end_date`, `city_code`, `city_name`, `zone_number`, `auto_created` (nullable bool).
- [x] 8.2 Add `GET /vehicles/{vehicle_id}/ser-tickets` to `src/mobility_manager/presentation/api/routers/vehicles.py`, mirroring `list_location_history`: `limit` (default 5, 1-50), `offset` (default 0, >=0), `require_owned_vehicle` dependency, rate limiting consistent with the sibling endpoint. Returns every ticket for the vehicle (no `auto_created` filter). Resolve `city_name` via the existing cities repository/lookup keyed on each ticket's `city_code` (null-safe when `city_code` is `None` or unmatched).
- [x] 8.3 Wire `ListSerTickets` into `app.py`'s state construction, following the same pattern as `list_vehicle_location_history`.
- [x] 8.4 Add `tests/presentation/test_vehicles_api.py` (or extend it) covering: happy path with pagination, mixed auto-created/manual tickets both returned, 401 unauthenticated, 403 non-owner, 404 non-existent vehicle, empty page for a vehicle with zero tickets, limit/offset validation (422), and city-name resolution (known code, null code, unmatched code).

## 9. Frontend: API layer and types

- [x] 9.1 Add `SerTicket` (including `auto_created: boolean | null`) and `SerTicketHistoryPage` types to `frontend/src/types/vehicle.ts`; add `has_ser_tickets: boolean` to `VehicleListItem`.
- [x] 9.2 Add `getSerTicketHistory(vehicleId, { limit, offset })` to `frontend/src/api/vehicles.ts`, following `getVehicleLocationHistory`'s exact shape (plain `fetch`, `credentials: "include"`, `URLSearchParams`).

## 10. Frontend: button and modal

- [x] 10.1 In `VehicleCard.tsx`, add a "View SER tickets" button rendered only when `vehicle.has_ser_tickets` is `true`, with an `onViewSerTickets(vehicle: VehicleListItem)` prop, following the exact conditional pattern used for the location-history button.
- [x] 10.2 In `MyVehiclesPage.tsx`, add `serTicketsVehicle` state + handler, and conditionally mount a new `VehicleSerTicketHistoryModal` when set, mirroring `historyVehicle`.
- [x] 10.3 Add `frontend/src/components/VehicleSerTicketHistoryModal.tsx`: paginated list (5 per page, "Load more") of every ticket for the vehicle (auto-created and manual mixed, newest first). Each entry renders a small Leaflet `MapContainer`/`TileLayer` centered via `setView`/`fitBounds` on that ticket's `(latitude, longitude)` with a single marker when both are non-null (reuse `VehicleLocationHistoryModal`'s marker icon/styling; no `Polyline`, no bearing/arrow logic) — when either is `null`, omit the map for that entry instead of rendering a default-coordinate marker. Each entry also shows start date, end date, city (prefer `city_name`, fall back to `city_code`, then a localized "unknown" placeholder), zone number, and a provenance label derived from `auto_created`: localized "Automatic" (`true`), "Manual" (`false`), or "Unknown" (`null`). Dates formatted via the same display-timezone resolution helper already used by `VehicleLocationHistoryModal`.
- [x] 10.4 Add loading/error/empty states consistent with `VehicleLocationHistoryModal`'s conventions.

## 11. i18n

- [x] 11.1 Add a `modal.serTickets.*` namespace (title, loading, loadMore, loadingMore, empty, error, startDate, endDate, city, zone, unknownCity, provenanceAuto, provenanceManual, provenanceUnknown) to `frontend/public/locales/en/translation.json` and the mirrored Spanish translations to `frontend/public/locales/es/translation.json`.
- [x] 11.2 Add a `vehicle.viewSerTickets` button-label key to both locale files.

## 12. Frontend tests

- [x] 12.1 Add/extend a Vitest suite for `VehicleCard` asserting the button renders when `has_ser_tickets` is `true` (including the vehicle-has-only-manual-tickets case) and is absent when `false`.
- [x] 12.2 Add a Vitest suite for `VehicleSerTicketHistoryModal`: initial page load, load-more pagination and hiding when exhausted, single-marker-no-polyline rendering, map omitted when coordinates are null, city fallback chain (name → code → placeholder), provenance label for each of `true`/`false`/`null`, and date formatting.

## 13. Full verification

- [x] 13.1 Run `make coverage` — confirm `domain/` stays at 100% and `application/` stays ≥80% with the new fields/use case included. (domain/application each measure at 99% — the only 2 missed lines in each are pre-existing tombstone stubs, `domain/ports/parking_service.py` and `application/use_cases/get_parking_ticket.py`, unrelated to this change and already uncovered before it; every file touched by this change is at 100%.)
- [x] 13.2 Run `make test` (full suite, backend and frontend) — all non-integration tests green; integration tests skipped without `POSTGRES_DSN` or run against the local docker-compose Postgres per AGENTS.md. (Backend: 928 passed, 147 integration tests skipped — local docker-compose Postgres was unreachable this session (colima/docker daemon not running) so `POSTGRES_DSN` was left unset per AGENTS.md. Frontend: 108 passed via `npx vitest run`, plus `tsc --noEmit` and `eslint src/` clean.)
- [ ] 13.3 Manually verify end-to-end: create both an automatic ticket (or seed one with `auto_created=true`) and a manual ticket via `POST /parking/ser-tickets` for the same vehicle, confirm the "View SER tickets" button appears, open the modal, and confirm both tickets show with correct maps, dates, city, zone, and provenance labels in both `en` and `es`. (NOT DONE — requires a running browser/app instance; left unchecked intentionally, no browser tooling available in this session.)

## 14. Fixes from code review (post-implementation)

A `/code-review high` pass (8 finder angles + verification) on the implemented diff surfaced 6 findings; the user asked for all 6 to be fixed, plus an index to keep task 14.7's per-vehicle existence check cheap (the N+1 query pattern itself is being kept as-is, matching the already-accepted precedent for the per-vehicle location lookup in the same use case).

- [x] 14.1 Add a secondary sort key (`id`, ascending, as a stable tiebreaker) to `list_by_vehicle`'s `order_by` in `PostgresParkingTicketRepository` (`parking_ticket_repo.py`), matching `PostgresVehicleLocationRepository.list_history`'s `recorded_at DESC, received_at DESC` tiebreaker pattern — so pagination stays deterministic when multiple tickets share the same `created_at`. Add/extend an integration test with two tickets sharing an identical `created_at` to prove no duplication/skipping across pages.
- [x] 14.2 Add an alembic migration creating an index on `parking_tickets(vehicle_id)` (e.g. `ix_parking_tickets_vehicle_id`), following the naming/style of `ix_vehicle_locations_vehicle_recorded` in `f3a4b5c6d1e2_create_vehicle_locations.py` — keeps `list_by_vehicle` and `has_any_for_vehicle` cheap (index scan, not seq scan) as `parking_tickets` grows. No application-code change needed for this task; it only touches the DB schema.
- [x] 14.3 Extract a shared root component (e.g. `HistoryModal.tsx`) from `VehicleLocationHistoryModal.tsx` and `VehicleSerTicketHistoryModal.tsx` covering their common logic: the saved-timezone-preference fetch effect + `resolveDisplayTimezone` memo, the initial-load effect scaffolding (cancellation guard, loading/error state), the `handleLoadMore` pagination state machine (offset/hasMore/loadingMore), the dialog shell (`role="dialog"`, `aria-modal`, header with title + cancel button, overlay/container classes), and the shared `OSM_FALLBACK`/`PAGE_SIZE` constants. Both modals should compose on top of it via children/render-props, each supplying only their per-item rendering (polyline+arrows+list rows vs single-marker-map+ticket details+provenance label) and their own fetch function (`getVehicleLocationHistory` vs `getSerTicketHistory`). Update both modals' existing test suites to keep passing against the refactored structure.
- [x] 14.4 Remove `test_vehicle_with_only_manual_tickets_reports_has_ser_tickets_true` from `tests/presentation/test_vehicles_api.py` — byte-identical to `test_vehicle_with_auto_created_ticket_reports_has_ser_tickets_true`, doesn't exercise a distinct scenario at the router layer (the manual-vs-auto distinction is already covered where it actually matters, in `test_list_user_vehicles.py`).
- [x] 14.5 Simplify `city_name=city_names.get(item.city_code) if item.city_code is not None else None` in `vehicles.py`'s `list_ser_tickets` handler to `city_name=city_names.get(item.city_code)` — `dict.get(None)` on a string-keyed dict already returns `None`, so the ternary is redundant.
- [x] 14.6 Change the provenance badge's colors in `VehicleSerTicketHistoryModal.tsx` (or the extracted shared component, if 14.3 lands first) so "Automatic"/"Manual"/"Unknown" are visually distinguishable, not all sharing the same `bg-blue-100 text-blue-700` classes already used elsewhere for the brand tag. No existing green/amber usage exists in the frontend yet, so introduce them here: e.g. `bg-green-100 text-green-700` for Automatic, keep `bg-gray-100 text-gray-700` (already the app's neutral-badge convention) for Manual, `bg-amber-100 text-amber-700` for Unknown. Update the modal's Vitest suite to assert the right class per state if reasonable.
- [x] 14.7 Run `make coverage` and `make test` (backend + frontend) — confirm everything still passes/meets thresholds after 14.1-14.6.
