## 1. Backend — repository

- [x] 1.1 Add `list_history(vehicle_id: UUID, limit: int, offset: int) -> tuple[list[VehicleLocation], bool]` to the `VehicleLocationRepository` port (`src/mobility_manager/domain/ports/vehicle_location_repository.py`)
- [x] 1.2 Implement `list_history` in `PostgresVehicleLocationRepository` (`src/mobility_manager/infrastructure/repositories/postgres/vehicle_location_repo.py`): query `ORDER BY recorded_at DESC OFFSET :offset LIMIT :limit + 1`, set `has_more = len(rows) > limit`, trim the extra row before returning
- [x] 1.3 Unit/integration tests for `list_history`: newest-first ordering, `has_more` true/false boundary, out-of-range offset returns empty list with `has_more=False`

## 2. Backend — use case

- [x] 2.1 Add `ListVehicleLocationHistory` use case (`src/mobility_manager/application/use_cases/list_vehicle_location_history.py`) that verifies vehicle ownership (mirror `GetLatestVehicleLocation`), then delegates to `list_history` — see Deviations: `GetLatestVehicleLocation` itself has no ownership logic (ownership is enforced by the router's `require_owned_vehicle` dependency), so this use case mirrors that thin-wrapper shape instead of duplicating ownership checks; router-level tests (3.3) cover 401/403/404
- [x] 2.2 Tests: owner success path (page + has_more delegated from repo), limit/offset delegation; non-owner/non-existent-vehicle 403/404 covered at router level (3.3) — see 2.1 deviation note

## 3. Backend — API

- [x] 3.1 Add `VehicleLocationHistoryResponse` schema (`items: list[VehicleLocationResponse]`, `has_more: bool`) to `src/mobility_manager/presentation/api/schemas.py` (actual path — no `routers/` subdirectory exists for schemas.py; corrected from tasks.md's stated path)
- [x] 3.2 Add `GET /vehicles/{vehicle_id}/locations` route in `src/mobility_manager/presentation/api/routers/vehicles.py`, with `limit` (default 5, ge=1, le=50) and `offset` (default 0, ge=0) query params validated via FastAPI/Pydantic constraints; auth + ownership checks matching `GET /vehicles/{vehicle_id}/location` (401/403/404). Wired via `app.state.list_vehicle_location_history` in `app.py`.
- [x] 3.3 Route/integration tests: default pagination, second page via offset, limit above max → 422, negative offset → 422, unauthenticated → 401, non-owner → 403, unknown vehicle → 404, vehicle with zero locations → 200 with empty `items`

## 4. Frontend — API client and types

- [x] 4.1 Add `VehicleLocationHistoryPage` type (`items: VehicleLocation[]`, `has_more: boolean`) to `frontend/src/types/vehicle.ts`
- [x] 4.2 Add `getVehicleLocationHistory(vehicleId, { limit, offset })` to `frontend/src/api/vehicles.ts` calling `GET /vehicles/{id}/locations`

## 5. Frontend — history modal

- [x] 5.1 Create `frontend/src/components/VehicleLocationHistoryModal.tsx`: accepts a vehicle, loads the first page on mount, holds accumulated `locations` (newest-first) + `offset` + `hasMore` state
- [x] 5.2 Render a Leaflet map (reuse conventions from `VehicleMap.tsx`) with one marker per loaded location; build the polyline from a reversed (chronological) copy of `locations`
- [x] 5.3 Give the newest location's marker a distinct icon/style from older markers (reuse the car `DivIcon` pattern from `VehicleMap.tsx` for the newest; plain circle markers for the rest)
- [x] 5.4 Wire marker click → popup showing that location's `recorded_at`
- [x] 5.5 Render the paired list below the map (newest first): timestamp + coordinates per row
- [x] 5.6 Add "Load more" control: fetches next page with incremented `offset`, appends to `locations`, updates `hasMore`; hidden/disabled when `hasMore` is false
- [x] 5.7 Empty state: vehicle with zero recorded locations shows a localised message instead of map/list
- [x] 5.8 Add i18n strings (en/es) for modal title, load more, empty state

## 6. Frontend — wiring into My Vehicles

- [x] 6.1 In `VehicleCard.tsx`, make the location line clickable (only when `vehicle.location` is present) via a new `onViewHistory` prop; non-clickable when no location
- [x] 6.2 In `MyVehiclesPage.tsx`, add `historyVehicle` state and render `{historyVehicle && <VehicleLocationHistoryModal vehicle={historyVehicle} onClose={...} />}`, following the existing `AddVehicleModal`/`EditVehicleModal` pattern
- [x] 6.3 Confirm the existing shared `VehicleMap` overview on `MyVehiclesPage` is untouched — verified: `VehicleMap`/`vehicles` block unchanged, only new modal state and `VehicleCard` prop added

## 7. Verification

- [ ] 7.1 Manually verify against the running stack: open history for a vehicle with >5 locations, confirm map pins + polyline + newest-pin distinction + popup timestamps + list pairing, click "Load more" through to exhaustion, confirm control disappears
- [ ] 7.2 Verify empty state for a vehicle with no locations, and that the location line is non-clickable in that case
- [x] 7.3 Run backend and frontend test suites — backend: `pytest tests/` (with local Postgres via `docker compose up -d postgres`) → 828 passed, 1 pre-existing/unrelated failure (`test_ser_enforcement_calendar_migrations_integration.py`, fails identically on the pre-change commit — stale local Postgres volume, not caused by this change). Frontend: no test runner is configured in this repo (no vitest/jest, no `.test.tsx` files anywhere) — ran `npm run type-check`, `npm run lint`, and `npm run build` instead, all pass.
