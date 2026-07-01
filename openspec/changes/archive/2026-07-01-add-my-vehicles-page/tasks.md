## 1. Database Migration — ON DELETE CASCADE

- [x] 1.1 Create Alembic migration that drops and recreates `vehicle_configs.vehicle_id` FK with `ON DELETE CASCADE`
- [x] 1.2 Extend same migration to drop and recreate `vehicle_locations.vehicle_id` FK with `ON DELETE CASCADE`
- [x] 1.3 Verify migration is reversible (`downgrade` function restores original FK constraints)

## 2. Domain — Repository Port Extension

- [x] 2.1 Add `get_all_by_user_id(user_id: UUID) -> list[Vehicle]` abstract method to `VehicleRepository` port in `domain/ports/vehicle_repository.py`

## 3. Infrastructure — Repository Implementation

- [x] 3.1 Implement `get_all_by_user_id` in `PostgresVehicleRepository` with a `SELECT ... WHERE user_id = :user_id` query

## 4. Application — Use Cases

- [x] 4.1 Create `application/use_cases/list_user_vehicles.py` — fetches vehicles by user_id, enriches each with latest location (null if none); returns a list of dataclass/named-tuple combining Vehicle + VehicleLocation | None
- [x] 4.2 Create `application/use_cases/delete_vehicle.py` — verifies ownership (403 if mismatch), deletes the vehicle row (cascade handles child rows); raises VehicleNotFoundError if not found
- [x] 4.3 Create `application/use_cases/update_vehicle.py` — verifies ownership, updates `vehicles.display_name`; for Toyota re-encrypts config only if new password is provided; for Generic updates display_name only

## 5. Presentation — API Schemas

- [x] 5.1 Add `VehicleLocationSummary` schema (latitude, longitude, recorded_at) to `schemas.py`
- [x] 5.2 Add `VehicleListItem` schema (vehicle_id, brand, display_name, vin, location: VehicleLocationSummary | None) for `GET /vehicles` response
- [x] 5.3 Add `ToyotaConfigResponse` schema (username, locale, password always `"●●●●●●●●"`) and `GenericConfigResponse` schema (location_token) to `schemas.py`
- [x] 5.4 Add `VehicleDetailResponse` schema (vehicle_id, brand, display_name, vin, config: ToyotaConfigResponse | GenericConfigResponse) for `GET /vehicles/{id}` and `PUT /vehicles/{id}` responses
- [x] 5.5 Add `UpdateToyotaRequest` schema (brand: Literal[TOYOTA], display_name, username, locale, password: str | None = None) to `schemas.py`
- [x] 5.6 Add `UpdateGenericRequest` schema (brand: Literal[GENERIC], display_name) to `schemas.py`
- [x] 5.7 Add `UpdateVehicleRequest` discriminated union (UpdateToyotaRequest | UpdateGenericRequest) to `schemas.py`

## 6. Presentation — API Endpoints

- [x] 6.1 Add `GET /vehicles` endpoint in `routers/vehicles.py` — requires auth, calls `list_user_vehicles` use case, returns `list[VehicleListItem]`
- [x] 6.2 Add `GET /vehicles/{vehicle_id}` endpoint — requires auth, checks ownership, reads vehicle + config from repos, returns `VehicleDetailResponse` with password masked
- [x] 6.3 Add `DELETE /vehicles/{vehicle_id}` endpoint — requires auth, calls `delete_vehicle` use case, returns 204
- [x] 6.4 Add `PUT /vehicles/{vehicle_id}` endpoint — requires auth, accepts `UpdateVehicleRequest` discriminated body, calls `update_vehicle` use case, returns `VehicleDetailResponse`
- [x] 6.5 Wire `list_user_vehicles`, `delete_vehicle`, and `update_vehicle` use cases into `app.state` in `main.py` (or wherever the app factory lives)

## 7. Backend Tests

- [x] 7.1 Unit tests for `ListUserVehiclesUseCase` — empty list, vehicles without location, vehicles with location
- [x] 7.2 Unit tests for `DeleteVehicleUseCase` — success, not found (404), wrong owner (403)
- [x] 7.3 Unit tests for `UpdateVehicleUseCase` — Toyota update with and without new password, Generic update, not found, wrong owner
- [x] 7.4 Integration test for `PostgresVehicleRepository.get_all_by_user_id` — two users, verify isolation
- [x] 7.5 API tests for `GET /vehicles` — authenticated (empty, with vehicles), unauthenticated (401)
- [x] 7.6 API tests for `GET /vehicles/{id}` — owner gets detail with masked password, non-owner (403), not found (404)
- [x] 7.7 API tests for `DELETE /vehicles/{id}` — owner deletes (204, cascade confirmed), non-owner (403), not found (404)
- [x] 7.8 API tests for `PUT /vehicles/{id}` — Toyota update (display_name only, full credentials), Generic update, non-owner (403), not found (404)

## 8. Frontend — Types and API Module

- [x] 8.1 Create `frontend/src/types/vehicle.ts` with `Vehicle`, `VehicleListItem`, `VehicleLocation`, `ToyotaConfig`, `GenericConfig`, `VehicleDetail` interfaces matching backend schemas
- [x] 8.2 Create `frontend/src/api/vehicles.ts` with `listVehicles()`, `getVehicle(id)`, `createVehicle(body)`, `updateVehicle(id, body)`, `deleteVehicle(id)` using `fetch` with `credentials: "include"`

## 9. Frontend — Components

- [x] 9.1 Create `frontend/src/components/VehicleMap.tsx` — single Leaflet MapContainer, renders a `🚗` DivIcon marker for each vehicle with a known location; popup shows display_name; fits bounds to all markers
- [x] 9.2 Create `frontend/src/components/VehicleCard.tsx` — displays vehicle metadata, brand-specific config (Toyota: username/locale/vin/masked-pw; Generic: constructed push URL), last coordinates or "No location data", Edit and Delete buttons
- [x] 9.3 Create `frontend/src/components/AddVehicleModal.tsx` — brand selector then brand-specific fields; calls `createVehicle`; closes on success; shows inline error on failure
- [x] 9.4 Create `frontend/src/components/EditVehicleModal.tsx` — pre-fills from `VehicleDetail`; Toyota shows username/locale/vin + optional password; Generic shows display_name only; calls `updateVehicle`; closes on success

## 10. Frontend — Page and Routing

- [x] 10.1 Create `frontend/src/pages/MyVehiclesPage.tsx` — fetches vehicle list on mount, renders VehicleMap + vehicle cards, Add Vehicle button; handles loading and error states
- [x] 10.2 Add `/my-vehicles` route in `frontend/src/App.tsx` wrapped in `ProtectedRoute`
- [x] 10.3 Add "My Vehicles" link to `frontend/src/components/Nav.tsx` — visible only when `user` is not null

## 11. E2E Tests (Playwright)

- [x] 11.1 Add `data-testid="vehicle-card"` to each vehicle card root element in `VehicleCard.tsx`
- [x] 11.2 Add `data-testid="error"` or `role="alert"` to inline error messages in AddVehicleModal, EditVehicleModal, and MyVehiclesPage
- [x] 11.3 Verify `frontend/e2e/my-vehicles.spec.ts` passes — all 20 scenarios across auth guard, nav, cards, map, add, edit, and delete
- [x] 11.4 Verify `frontend/e2e/map.spec.ts` still passes after auth fixture refactor
