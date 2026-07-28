## MODIFIED Requirements

### Requirement: ParkingTicket entity represents a created SER ticket
The system SHALL define a `ParkingTicket` domain entity with fields: `id` (UUID), `vehicle_id` (UUID), `user_id` (UUID), `provider` (str), `duration_minutes` (int), `provider_reference` (str or None), `cost` (float), `end_date` (datetime), `created_at` (datetime), `city_code` (str or None), `zone_number` (str or None), `latitude` (float or None), `longitude` (float or None), `auto_created` (bool or None). `city_code` and `zone_number` identify the SER zone the ticket was created for; both SHALL be populated by every ticket-creating code path going forward and SHALL only be `None` for tickets persisted before these fields were introduced (whose original zone cannot be recovered). `latitude` and `longitude` SHALL be populated with the coordinates of the `GeoLocation` used to create the ticket, by every ticket-creating code path going forward, and SHALL only be `None` for tickets persisted before these fields were introduced. `auto_created` SHALL be `True` when the ticket was created by `SerTicketCreationTriggerHandler` or `False` when created via `POST /parking/ser-tickets` — the only two ticket-creation paths — populated by every ticket-creating code path going forward, and SHALL only be `None` for tickets persisted before this field was introduced.

#### Scenario: ParkingTicket entity is immutable value object
- **WHEN** a `ParkingTicket` is constructed
- **THEN** its fields cannot be reassigned after construction

#### Scenario: ParkingTicket created via any provider carries its resolved coordinates
- **WHEN** a `ParkingTicket` is created via any concrete `SerTicketProviderPort.create_ticket` implementation, resolved against a `GeoLocation` with `lat=40.4, lng=-3.7`
- **THEN** the persisted `ParkingTicket` has `latitude=40.4` and `longitude=-3.7`

#### Scenario: Pre-existing tickets keep null coordinates and auto_created
- **WHEN** a `ParkingTicket` row was persisted before `latitude`, `longitude`, and `auto_created` existed
- **THEN** reading that row back yields `latitude=None`, `longitude=None`, `auto_created=None`

---

### Requirement: parking_tickets table persists created tickets
The system SHALL create a `parking_tickets` table with columns: `id UUID PRIMARY KEY`, `vehicle_id UUID NOT NULL REFERENCES vehicles(id)`, `user_id UUID NOT NULL REFERENCES users(id)`, `provider TEXT NOT NULL`, `duration_minutes INT NOT NULL`, `provider_reference TEXT`, `created_at TIMESTAMP WITH TIME ZONE NOT NULL`, `latitude DOUBLE PRECISION` (nullable), `longitude DOUBLE PRECISION` (nullable), `auto_created BOOLEAN` (nullable).

#### Scenario: parking_tickets table schema
- **WHEN** the migration is applied
- **THEN** the `parking_tickets` table exists with all columns, `provider_reference`, `latitude`, `longitude`, and `auto_created` nullable

#### Scenario: Migration adds new columns without affecting existing rows
- **WHEN** the migration adding `latitude`, `longitude`, and `auto_created` to `parking_tickets` is applied
- **THEN** existing rows are unaffected and read back with `latitude=NULL`, `longitude=NULL`, `auto_created=NULL`

---

### Requirement: CreateSerTicket use case orchestrates ticket creation
The system SHALL define a `CreateSerTicket` use case with `execute(user_id: UUID, vehicle_id: UUID, provider: str, duration_minutes: int, location: GeoLocation | None = None, auto_created: bool = False) -> ParkingTicket`, which verifies the vehicle belongs to `user_id`, loads the stored session for `(user_id, provider)`, resolves the provider instance from the registry, resolves `location` (using the given value if provided, otherwise the vehicle's latest known location via `GetLatestVehicleLocation`), calls `create_ticket(session, vehicle, duration_minutes, location)`, persists the returned `ParkingTicket` — with `latitude`/`longitude` set from the resolved `location` and `auto_created` set from the `auto_created` argument — via `ParkingTicketRepository`, and returns it.

#### Scenario: Successful ticket creation with an explicit location
- **WHEN** `CreateSerTicket.execute` is called for a vehicle owned by `user_id`, with a valid stored session for `provider` and an explicit `location`
- **THEN** the provider's `create_ticket` is called with the decrypted session, the vehicle, the duration, and that exact `location`
- **THEN** the returned `ParkingTicket` is persisted and returned to the caller, with `latitude`/`longitude` matching the explicit `location`

#### Scenario: Successful ticket creation falls back to the vehicle's latest known location
- **WHEN** `CreateSerTicket.execute` is called without a `location` argument, and the vehicle has a recorded location history
- **THEN** the provider's `create_ticket` is called with the vehicle's latest known `GeoLocation`
- **THEN** the persisted `ParkingTicket`'s `latitude`/`longitude` match that fallback location

#### Scenario: Vehicle not owned by user is rejected
- **WHEN** `CreateSerTicket.execute` is called with a `vehicle_id` that does not belong to `user_id`
- **THEN** the use case raises an error without calling any provider

#### Scenario: No session found for provider is rejected
- **WHEN** `CreateSerTicket.execute` is called for a `(user_id, provider)` pair with no stored session
- **THEN** the use case raises an error without calling the provider's `create_ticket`

#### Scenario: Vehicle not present in the provider publishes an event
- **WHEN** the provider's `create_ticket` raises `SerProviderVehicleNotFoundError`
- **THEN** `CreateSerTicket` publishes a `VehicleNotPresentInSerTicketProvider` event carrying `vehicle_id`, `user_id`, and `provider` via the injected `EventPublisher`
- **THEN** the original error is re-raised to the caller

#### Scenario: Default auto_created is False
- **WHEN** `CreateSerTicket.execute` is called without an `auto_created` argument
- **THEN** the persisted `ParkingTicket` has `auto_created=False`

#### Scenario: Explicit auto_created is persisted
- **WHEN** `CreateSerTicket.execute` is called with `auto_created=True`
- **THEN** the persisted `ParkingTicket` has `auto_created=True`
