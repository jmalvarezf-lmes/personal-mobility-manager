## Why

SER ticket creation needs a provider abstraction before any concrete implementation can be built — different city/operator apps have different login and ticket-creation mechanics, and credentials are tied to the user (not the vehicle, unlike vehicle location providers). This change defines that abstraction end-to-end (port, provider registry, per-user credential storage, and the use cases that call it) plus the event-driven plumbing that will eventually trigger ticket creation from a vehicle location update — all wired together and unit-tested against a fake provider, but with no concrete provider and no real trigger logic yet, so nothing user-facing changes.

## What Changes

- Add `SerTicketProviderPort` with `login(credentials: SerProviderCredentials) -> SerProviderSession` and `create_ticket(session: SerProviderSession, vehicle, duration_minutes) -> ParkingTicket`, plus a `SerTicketProviderRegistry` (mirrors `BrandRegistry`) that returns no providers until a concrete one is registered. `SerProviderCredentials`/`SerProviderSession` are thin domain value objects (mirroring `ToyotaConfig`) that wrap a provider-defined payload, keeping the port signature self-documenting even though the payload contents remain opaque until a concrete provider exists.
- Add per-user encrypted credential/session storage (`user_ser_provider_configs` table + repository), keyed by `(user_id, provider)`, mirroring `vehicle_configs`' encrypted-payload pattern but scoped to the user rather than the vehicle.
- Flesh out the currently-empty `ParkingTicket` entity and add a `ParkingTicketRepository` + `parking_tickets` table to persist created tickets.
- Add `ConnectSerTicketProvider` (calls `login`, persists the resulting session) and `CreateSerTicket` (resolves a user's provider config, calls `create_ticket`, persists the result) use cases. Neither is exposed over HTTP in this change — they're unit-tested against a fake provider only.
- Add an `EventPublisher` port with a synchronous, in-memory adapter, and a new `VehicleLocationUpdated` domain event published by `RecordVehicleLocation` after every successful location save (pull and push alike).
- Add a `SerTicketTriggerHandler`, registered against `VehicleLocationUpdated` at startup, with a no-op body — scaffolding for the future "check SER zone + user preference + maybe create a ticket" logic, deliberately not implemented yet.

## Capabilities

### New Capabilities
- `ser-ticket-provider`: Provider interface, registry, per-user credential storage, `ParkingTicket` persistence, and the connect/create use cases.
- `vehicle-location-events`: `EventPublisher` port, in-memory adapter, `VehicleLocationUpdated` event, and its no-op subscriber.

### Modified Capabilities
(none — `RecordVehicleLocation`'s event-publishing side effect is captured as part of the new `vehicle-location-events` capability rather than as a behavior change to `vehicle-location-pull`/`vehicle-location-push`, which remain about ingestion mechanics only)

## Impact

- **Database**: two new tables (`user_ser_provider_configs`, `parking_tickets`) + migrations.
- **Backend**: new domain port/entity/event files, new infrastructure registry/repositories/event adapter, two new application use cases + one event handler, changes to `record_vehicle_location.py` (publish event after save) and `app.py` (wire the event publisher, register the handler, wire new repositories).
- **No API surface changes** — nothing is reachable over HTTP in this change.
- **No behavior changes** — the event handler is a no-op, so no ticket is ever created and no existing flow's output changes.
