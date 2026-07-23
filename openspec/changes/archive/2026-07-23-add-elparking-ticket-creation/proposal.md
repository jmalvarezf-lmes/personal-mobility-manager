## Why

`SerTicketProviderPort.create_ticket()` and its ElParking implementation exist only as a stub (`NotImplementedError`) since `add-elparking-login-provider`, with no HTTP surface to trigger it. Users have no way to actually create a paid SER parking ticket through the app today. ElParking's real ticket-creation flow is a multi-step, time-sensitive chain (vehicle/town/zone/rate/pricing-step resolution followed by a signed, checksum-validated POST) that must stay entirely hidden behind the existing provider-agnostic port, so that a future non-ElParking provider — or the planned automatic-creation trigger from `VehicleLocationUpdated` — never needs to know ElParking's internals.

## What Changes

- Implement `ElParkingSerTicketProvider.create_ticket()` for real: resolves the vehicle's ElParking `id_vehicle` by license plate, resolves `id_ser_zone`/`id_ser_rate` for the vehicle's location via our own zone geometry plus a cached ElParking town/zone/rate ID-translation table, fetches the mandatory pricing/checksum step, and submits the ticket.
- Add `ElParkingClient`, a new infrastructure helper encapsulating all ElParking HTTP calls (login, logout, list vehicles, list towns, list zones, get pricing steps, create ticket), using the correct HTTP Basic auth (blank username, access token as password) plus the required `ep-app-name`/`ep-app-version` headers on every authenticated call.
- **Fix**: `ElParkingSerTicketProvider.logout()` currently sends `Authorization: Bearer <token>`, which is wrong — ElParking expects the same HTTP Basic scheme used by every other authenticated call. Corrected as part of moving `logout()` into `ElParkingClient`.
- Add a new infrastructure-only cache of ElParking's city → town/zone/rate ID mapping, keyed by `(city_code, provider)`, refreshed lazily on demand with a 30-day freshness window. This mapping is ElParking-specific vocabulary and never crosses the `SerTicketProviderPort` boundary.
- Widen `SerTicketProviderPort.create_ticket()` and `CreateSerTicket.execute()` to accept an explicit `location`, falling back to the vehicle's latest known location when no override is given.
- Extend `ParkingTicket` with `cost` and `end_date`, populated from ElParking's ticket-creation response.
- Add a new domain event `VehicleNotPresentInSerTicketProvider`, published by `CreateSerTicket` when the vehicle's license plate cannot be matched against the user's ElParking-registered vehicles — no handler ships in this change (mirrors how `VehicleLocationUpdated` shipped before `SerTicketTriggerHandler` existed).
- Expose `POST /parking/ser-tickets` (authenticated), accepting `vehicle_id`, `duration_minutes`, and an optional explicit `latitude`/`longitude` override, returning the created `ParkingTicket`. This endpoint is a manual/testing surface for this change, not the intended production trigger — the planned production path is automatic creation from `VehicleLocationUpdated` (a later change). Accordingly, it has no idempotency protection against a client retrying after a timeout (see design.md); this is acceptable only because it isn't meant to be a real client-facing surface yet.

## Capabilities

### New Capabilities
(none — this extends the existing `ser-ticket-provider` capability)

### Modified Capabilities
- `ser-ticket-provider`: `create_ticket` moves from a `NotImplementedError` stub to a real implementation; the port signature gains a `location` parameter; `ParkingTicket` gains `cost`/`end_date`; `logout()`'s auth scheme is corrected; a new HTTP endpoint (`POST /parking/ser-tickets`) is added; a new `VehicleNotPresentInSerTicketProvider` event is introduced.

## Impact

- `domain/ports/ser_ticket_provider.py`, `domain/entities/parking_ticket.py`, `domain/events/` (new event), `domain/exceptions.py` (new exception)
- `application/use_cases/create_ser_ticket.py`
- `infrastructure/ser_ticket_providers/elparking/` (new `client.py`, rewritten `provider.py`, new zone-mapping cache repository + Postgres adapter + migration)
- `presentation/api/routers/parking.py` (new endpoint), `presentation/api/schemas.py`
- New Alembic migrations: `ser_ticket_provider_zone_mappings` table, `parking_tickets` columns (`cost`, `end_date`)
- `app.py` wiring: `ElParkingSerTicketProvider` gains new constructor dependencies (`ser_zone_repo`, `city_repo`, the new mapping repository); `SerTicketProviderRegistry.build_providers()` signature changes accordingly
