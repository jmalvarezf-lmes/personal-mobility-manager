## Context

Generic vehicles (`Brand.GENERIC`) get their location exclusively through `POST /vehicles/{token}/location` (`vehicle-location-push` capability) — a token-authenticated endpoint meant for an external device or script to call. There is no way for the vehicle's owner to set a location from their own logged-in session in the app itself.

`VehicleCard.tsx` already exposes the raw push URL (including the token) to the owner for configuring their own device. The frontend has no precedent for using the Browser Geolocation API, and no existing modal is authenticated-but-vehicle-scoped in the way this one needs to be.

## Goals / Non-Goals

**Goals:**
- Let a generic vehicle's owner submit a location update from their own browser session — either via Geolocation autofill or manual lat/lng — without needing the device token.
- Reuse the existing `RecordVehicleLocation` use case unchanged, so persistence, dedup, and `VehicleLocationUpdated` event semantics stay identical to the device-push path.
- Follow existing UI and backend conventions exactly (modal shape, ownership-check dependency, rate-limiting posture).

**Non-Goals:**
- No support for Toyota (or any future non-generic) vehicles — those get location exclusively from their own backend integration.
- No change to the existing token-based device endpoint or its spec.
- No new `source` value — a manual/browser submission is recorded identically to a device push (`source="push"`); the distinction is in *who authenticated the request*, not in downstream data semantics, and `source` is not surfaced in any UI today.

## Decisions

**New authenticated endpoint, not a reuse of the token endpoint.** `POST /vehicles/{vehicle_id}/locations` (plural) is added alongside the existing `POST /vehicles/{token}/location` (singular). It uses `get_current_user` + `get_owned_vehicle_or_raise(request, vehicle_id, current_user)` — the exact dependency already used by `PUT /vehicles/{vehicle_id}` and the SER-parking-exemption routes — instead of a token lookup. Rejected alternative: have the frontend call the existing token endpoint directly using the token already shown in the UI. Rejected because it bypasses the session/ownership auth model the rest of the authenticated API surface uses, and keeps a sensitive token in frontend JS/network traffic unnecessarily.

**Path must be `locations` (plural), not `location` (singular) — this is load-bearing, not stylistic.** `RegisterVehicle` generates `location_token = str(uuid4())` (`application/use_cases/register_vehicle.py:120`), so a generic vehicle's token and its `vehicle_id` are both UUID-formatted strings — a `{vehicle_id:uuid}` path converter cannot distinguish them, and reusing the literal path `/{vehicle_id}/location` would collide with the existing `/{token}/location` route (identical URL shape, identical HTTP method — Starlette resolves by registration order, not by which typed converter "looks more specific", so this would silently misroute rather than error). Using the already-established plural `locations` segment (matching the existing `GET /vehicles/{vehicle_id}/locations` history endpoint) makes the two POST routes literally different path templates, avoiding the collision entirely. Also reads correctly as REST: POST to the `locations` collection creates a new entry in it.

**Generic-only, enforced with `400`.** The handler checks `vehicle.brand == Brand.GENERIC` after ownership resolution and raises `400` otherwise (not `403`/`404`, since the caller *does* own the vehicle — the request is simply invalid for this vehicle type). Toyota vehicles have no `location_token`/`GenericConfig`, so allowing this endpoint for them would create a second, conflicting source of truth for their location.

**Delegates to the same use case.** The new route body is structurally identical to the token endpoint's: resolve `vehicle_id`, call `RecordVehicleLocation.execute(vehicle_id, lat, lon, recorded_at, source="push")`. No new use case is introduced.

**Rate limiting mirrors both existing precedents.** Two limits apply, matching what already exists for sibling endpoints:
1. The standard `60/minute` per-remote-address limit already applied to other authenticated vehicle-mutation endpoints (`POST /vehicles`, `PUT /vehicles/{vehicle_id}`) per the `api-rate-limiting` capability.
2. The `1/minute` per-vehicle limit already applied to the token push endpoint — keyed by `vehicle_id` instead of `token` here. This exists because the `ser-ticket-auto-creation` capability's zone-transition gate can be retriggered by rapid location updates near a SER-zone boundary; that risk is in the shared `RecordVehicleLocation`/event pipeline, not the auth mechanism, so it applies equally here.

**Request/response schema reuse.** The new endpoint accepts the same `lat`/`lon`/`recorded_at` fields as `PushLocationRequest`. It reuses that Pydantic model directly (no new schema class) since the payload shape is identical; only the path parameter and auth differ. Response is `204 No Content`, matching the token endpoint.

**Frontend: single modal, geolocation as autofill (Shape A).** One modal (`SetVehicleLocationModal.tsx`, styled like `AddVehicleModal`/`EditVehicleModal`) with a "Use my current location" button that calls `navigator.geolocation.getCurrentPosition`, filling editable `lat`/`lng` number inputs on success. On denial/error the fields are simply left for manual entry with an inline message — no separate mode/tab. A single Save button submits whatever is currently in the fields, client-validated to the same `[-90, 90]`/`[-180, 180]` bounds as the backend. `recorded_at` sent as the current client time (Geolocation's own `position.timestamp` is not used, to keep the manual and geolocation-assisted paths behaviorally identical).

## Risks / Trade-offs

- **[Risk]** Browser geolocation accuracy varies widely (especially indoors/desktop) → **Mitigation**: fields stay editable after autofill; user can correct before saving.
- **[Risk]** Geolocation permission denial is a dead end with no manual fallback UI shown → **Mitigation**: manual lat/lng fields are always visible in the same form, not gated behind a successful geolocation call.
- **[Trade-off]** Reusing `PushLocationRequest` couples the two endpoints' request shape → acceptable since both ultimately feed the same use case with the same validation rules; introducing a duplicate schema would be pure duplication.

## Open Questions

None — the auth mechanism, generic-only restriction, and dialog shape were resolved during exploration.
