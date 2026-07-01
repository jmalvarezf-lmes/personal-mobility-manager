## Context

The backend already has vehicle registration (`POST /vehicles`), location push/pull, and Google OAuth authentication. The `Vehicle` entity carries `user_id` but there are no list, detail, update, or delete endpoints. The frontend has a working react-leaflet map (`ZoneMap`) and a protected route pattern (`ProtectedRoute`). Toyota credentials are stored AES-encrypted via Fernet; Generic vehicles carry a cleartext `location_token`. Foreign keys on `vehicle_configs` and `vehicle_locations` currently have no `ON DELETE CASCADE`.

## Goals / Non-Goals

**Goals:**
- Add `GET /vehicles`, `GET /vehicles/{id}`, `PUT /vehicles/{id}`, `DELETE /vehicles/{id}` to the backend
- Add a `My Vehicles` protected page with shared Leaflet map + vehicle cards
- Add full CRUD UI (create, edit, delete) for vehicles
- Add `ON DELETE CASCADE` migration to remove child rows when a vehicle is deleted
- Mask Toyota passwords in GET/detail responses

**Non-Goals:**
- Changing the vehicle registration (`POST /vehicles`) flow
- Changing how location data is pushed or pulled (scheduler, push endpoint)
- Real-time location updates (the map shows the last known fix, not a live feed)
- Pagination of the vehicle list (user vehicle count is expected to be small)

## Decisions

### D1: No new use case for list — inline in router vs. dedicated use case
**Decision**: Create a `ListUserVehiclesUseCase` that returns vehicles enriched with their latest location.

**Rationale**: Following existing pattern (every feature has a use case). Keeps the router thin. The use case fetches all vehicles via `vehicle_repo.get_all_by_user_id`, then for each vehicle calls `vehicle_location_repo.get_latest(vehicle_id)` (already exists). Acceptable N+1 since vehicle count per user is small.

**Alternative considered**: Query in a single JOIN at the repo level. Rejected — adds complexity against a small dataset; clean arch separates these queries.

---

### D2: Update request uses discriminated union by brand (same pattern as registration)
**Decision**: `PUT /vehicles/{id}` accepts `UpdateToyotaRequest | UpdateGenericRequest` discriminated by `brand`.

**Rationale**: Mirrors the existing `RegisterVehicleRequest` discriminated union. The brand is immutable so the client always knows which shape to send. Keeps validation clean and type-safe.

**Alternative considered**: Single flat request with optional fields. Rejected — makes the schema ambiguous (is `username` applicable to Generic?) and loses discriminated-union validation.

---

### D3: Toyota password update — empty string means "keep existing"
**Decision**: In `UpdateToyotaRequest`, `password` is `str | None` defaulting to `None`. If `None` or empty string, the use case does not re-encrypt; the existing `encrypted_payload` is preserved.

**Rationale**: Users editing display_name or locale shouldn't have to re-enter their Toyota password. The edit form sends empty string when the password field is left blank.

**Alternative considered**: Separate endpoint for credential update. Rejected — unnecessary complexity; one PUT per resource is conventional.

---

### D4: DB cascade via Alembic migration, not use-case manual deletion
**Decision**: New migration drops and recreates the FK constraints on `vehicle_configs.vehicle_id` and `vehicle_locations.vehicle_id` with `ON DELETE CASCADE`.

**Rationale**: DB-level cascade is atomic, correct under concurrent access, and removes the risk of partial deletion if the use case crashes mid-sequence. Simpler delete use case (just delete the vehicle row).

**Alternative considered**: Manual deletion order in the use case. Rejected — more code, race condition risk, violates single-responsibility.

---

### D5: Car icon on Leaflet map — DivIcon with emoji, not SVG file
**Decision**: Use a `L.divIcon` with `🚗` in a styled `<div>` as the car marker.

**Rationale**: No asset pipeline needed, zero new dependencies, visually distinct from the zone `CircleMarker` dots. The emoji is rendered by the browser font stack.

**Alternative considered**: Custom SVG file added to the assets directory. Rejected — adds an asset dependency; the emoji approach is sufficient for the MVP.

---

### D6: Frontend API module follows existing pattern
**Decision**: Add `frontend/src/api/vehicles.ts` with typed async functions (`listVehicles`, `getVehicle`, `createVehicle`, `updateVehicle`, `deleteVehicle`) using `fetch` with `credentials: "include"`.

**Rationale**: Consistent with `auth.ts` and `zones.ts`. No new HTTP library needed.

---

### D7: Edit and Add modals are separate components
**Decision**: `AddVehicleModal.tsx` and `EditVehicleModal.tsx` are separate components.

**Rationale**: Creation form starts with a brand selector and shows different required fields (Toyota requires password on create, Generic doesn't). Edit form pre-fills and makes password optional. Sharing state between these is more complex than two focused components.

---

### D8: Generic "push URL" is constructed client-side
**Decision**: The push URL shown in the Generic vehicle card is constructed in the frontend as `${window.location.origin}/api/vehicles/${location_token}/location`.

**Rationale**: The backend has no concept of its own public URL. The client knows the origin. No env var or config endpoint change needed.

## Risks / Trade-offs

- **N+1 location query in list endpoint** → Acceptable for small vehicle counts; document in code if optimisation is ever needed.
- **Migration alters FK constraints** → Requires a brief exclusive lock on `vehicle_configs` and `vehicle_locations`. Tables are small; downtime risk is negligible. Reversible via `alembic downgrade`.
- **Toyota password masking is response-only** → The actual credential is never returned. A determined user could register a new vehicle to store a different password, but they cannot recover the stored one through the API. Acceptable for this threat model.
- **Multiple Leaflet map instances** → Avoided by using a single shared map (Option B). Only `ZoneMap` and `VehicleMap` are on separate pages so there is no DOM conflict.

## Migration Plan

1. Apply Alembic migration (cascade FKs) before deploying new code — safe because the only change is the FK constraint; no data is moved.
2. Deploy backend with new endpoints.
3. Deploy frontend with new page and nav link.
4. Rollback: `alembic downgrade -1` restores FK constraints; remove the frontend route from `App.tsx`.

## Open Questions

- None — all design decisions resolved during exploration.
