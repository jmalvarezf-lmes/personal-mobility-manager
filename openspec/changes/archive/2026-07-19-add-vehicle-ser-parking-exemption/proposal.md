## Why

Vehicle owners who already pay a resident/area parking fee for a specific SER zone still get a "you need a SER ticket" notification every time their vehicle is located there, because the system has no way to record that a given vehicle is exempt in a given zone. This is a false-positive notification with no way to suppress it today.

## What Changes

- Add a new `vehicle_ser_parking_exemptions` table: at most one row per vehicle, storing the `(city_code, zone_number)` of the SER zone the owner has already paid to park in — a composite foreign key into `ser_zone_areas`, so only zones with a real, displayable neighbourhood can be selected.
- Add `GET /vehicles/{id}/ser-parking-exemptions`, `POST /vehicles/{id}/ser-parking-exemptions`, and `DELETE /vehicles/{id}/ser-parking-exemptions` to view, set/replace, and clear a vehicle's exemption.
- Add `GET /cities` (backed by the existing `cities` table) so the exemption picker's first step lists real, live cities instead of a hardcoded value.
- **BREAKING** (internal use case signature): `DetermineSerTicketRequirement.execute()` gains a required `vehicle_id: UUID` parameter. It now returns `False` when the vehicle has an exemption matching the containing zone's `(city_code, zone_number)`, in addition to the existing enforcement-schedule check. This replaces the "no signature change" seam recorded in the use case's current docstring/spec, which turns out to be unworkable for a per-vehicle fact.
- Update `SerTicketTriggerHandler` (the only current caller) to pass `vehicle_id` through to `DetermineSerTicketRequirement.execute()`.
- Remove `GET /parking/ser-zones`'s hardcoded `_SUPPORTED_CITIES = {"madrid"}` set; validate the `city` query parameter against the live `cities` table instead, so a newly-added city becomes queryable without a code change.
- Fix `GET /parking/ser-zones` to actually scope its `zones`/`frontiers` arrays to the requested city — today `SerZoneRepository.list_all()`/`list_zone_areas()` are unfiltered by `city_code` (invisible today only because Madrid is the only seeded city), and the new exemption picker depends on this being correct.
- Frontend: add a two-step picker (city, then SER zone — displayed by neighbourhood name) to the vehicle edit flow, letting an owner set or clear their vehicle's parking exemption.

## Capabilities

### New Capabilities
- `vehicle-ser-parking-exemption`: per-vehicle SER zone parking-fee exemption — storage, REST endpoints, and the city/zone picker UI.

### Modified Capabilities
- `ser-ticket-requirement`: `DetermineSerTicketRequirement.execute()` signature changes to accept `vehicle_id`, and a matching exemption now suppresses a required ticket.
- `ser-zone-ticket-notification`: `SerTicketTriggerHandler` now passes `vehicle_id` to `DetermineSerTicketRequirement`, so a vehicle's exemption suppresses the notification.
- `zones-bulk-query`: `GET /parking/ser-zones` validates `city` against the live `cities` table instead of a hardcoded set.
- `city-registry`: adds a `GET /cities` read endpoint over the existing `cities` table.

## Impact

- **Backend**: new migration + table, new domain entity/port/repository, new use-case dependency wiring in `app.py`, new `vehicles` sub-router, changed `zones.py` city validation, changed `DetermineSerTicketRequirement` and its one caller (`SerTicketTriggerHandler`) plus their existing tests.
- **Frontend**: new API client calls, a new picker UI in the vehicle edit flow (`EditVehicleModal.tsx` or adjacent), new i18n strings.
- **No breaking changes to any external/public HTTP contract** — the breaking signature change is internal to the `DetermineSerTicketRequirement` use case, which has a single caller in this codebase.
