## Why

Generic vehicles currently only receive location updates via an external device pushing to a bespoke per-vehicle token URL (`POST /vehicles/{token}/location`). A user who simply wants to record their car's current position right now — from their own phone or laptop, with no separate GPS hardware — has no way to do that from the app itself.

**Note:** `POST /vehicles/{token}/location` is separately pending a decision to change its authorization model to a secret known only to the vehicle/device provider, for stronger security than an unauthenticated URL-embedded token. That is out of scope for this change and tracked separately, but is noted here because it means the token endpoint's contract is expected to change independently of the new endpoint introduced below — the two SHALL remain distinct routes (see `What Changes`) specifically so this change is unaffected by that future decision.

## What Changes

- New session-authenticated endpoint `POST /vehicles/{vehicle_id}/locations` (plural — deliberately distinct from the existing singular `POST /vehicles/{token}/location`, since `location_token` values are themselves UUID-formatted and would otherwise collide with `vehicle_id` on the same route shape) that lets the vehicle's owner submit a location update directly. It reuses the same `RecordVehicleLocation` use case as the existing device-token push endpoint (same validation, dedup, and event publishing), but resolves the vehicle via `get_owned_vehicle_or_raise` (session + ownership) instead of a token.
- The new endpoint is restricted to `GENERIC` vehicles; requests for a `TOYOTA` vehicle are rejected with `400` (Toyota vehicles get location exclusively from the Toyota backend poll).
- `VehicleCard` gains a "Set location" action, shown only for generic vehicles, opening a modal with a "Use my current location" button (Browser Geolocation API, autofills editable lat/lng fields) and manual lat/lng entry as a fallback/override, following the existing `AddVehicleModal`/`EditVehicleModal` pattern.
- New frontend API client function to call the endpoint.

## Capabilities

### New Capabilities
- `vehicle-location-manual-entry`: session-authenticated endpoint allowing a generic vehicle's owner to submit a location update for their own vehicle, delegating to the existing `RecordVehicleLocation` use case.

### Modified Capabilities
- `vehicle-management-ui`: vehicle cards for generic vehicles gain a "Set location" action opening a dialog to set the vehicle's location via browser geolocation or manual lat/lng entry.

## Impact

- **Backend**: new route in `presentation/api/routers/vehicles.py`; reuses `RecordVehicleLocation` use case and `get_owned_vehicle_or_raise` dependency; no new domain/persistence code, no schema migration (writes to the existing `vehicle_locations` table with `source="push"`).
- **Frontend**: new modal component alongside `AddVehicleModal`/`EditVehicleModal`; new button in `VehicleCard.tsx` (generic vehicles only); new function in `frontend/src/api/vehicles.ts`; new i18n strings (en/es).
