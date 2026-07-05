## ADDED Requirements

### Requirement: ParkingTicket entity represents a created SER ticket
The system SHALL define a `ParkingTicket` domain entity with fields: `id` (UUID), `vehicle_id` (UUID), `user_id` (UUID), `provider` (str), `duration_minutes` (int), `provider_reference` (str or None), `created_at` (datetime).

#### Scenario: ParkingTicket entity is immutable value object
- **WHEN** a `ParkingTicket` is constructed
- **THEN** it is a frozen dataclass (or equivalent) with all six fields populated (`provider_reference` may be `None`)

---

### Requirement: SerProviderCredentials and SerProviderSession value objects
The system SHALL define `SerProviderCredentials` and `SerProviderSession` as frozen domain value objects, each wrapping a single `data: dict[str, Any]` field. Neither value object SHALL constrain the shape of `data` — each concrete provider defines its own contents, following the same convention as `ToyotaConfig`/`GenericConfig` (a named, typed value crosses the port boundary rather than a bare dict).

#### Scenario: Value objects are immutable wrappers
- **WHEN** a `SerProviderCredentials` or `SerProviderSession` is constructed
- **THEN** it is a frozen dataclass (or equivalent) holding exactly the `data` dict it was given, unmodified

---

### Requirement: SerTicketProviderPort defines login and ticket creation
The system SHALL define a `SerTicketProviderPort` abstract interface with:
- `login(credentials: SerProviderCredentials) -> SerProviderSession` — authenticates with the provider and returns a session
- `create_ticket(session: SerProviderSession, vehicle: Vehicle, duration_minutes: int) -> ParkingTicket` — creates a parking ticket for the given vehicle using a previously obtained session

#### Scenario: Port is implementation-agnostic
- **WHEN** a concrete class implements `SerTicketProviderPort`
- **THEN** it may define any internal structure for the `data` dict inside the `SerProviderCredentials` it expects and the `SerProviderSession` it returns from `login`, without changing the port's method signatures

---

### Requirement: SerTicketProviderRegistry resolves provider instances
The system SHALL define a `SerTicketProviderRegistry` that returns the set of currently available `SerTicketProviderPort` implementations, keyed by provider name. The registry SHALL return an empty result when no concrete provider is registered — this SHALL NOT be treated as an error.

#### Scenario: No providers registered yet
- **WHEN** `SerTicketProviderRegistry` is queried and no concrete provider has been registered
- **THEN** it returns an empty mapping, and callers (e.g. `ConnectSerTicketProvider`) treat "provider not found" as an expected, handleable condition rather than a crash

---

### Requirement: user_ser_provider_configs table persists per-user provider sessions
The system SHALL create a `user_ser_provider_configs` table with columns: `user_id UUID NOT NULL REFERENCES users(id)`, `provider TEXT NOT NULL`, `encrypted_payload BYTEA NOT NULL`, `updated_at TIMESTAMP WITH TIME ZONE NOT NULL`, with a composite primary key on `(user_id, provider)`.

#### Scenario: user_ser_provider_configs table schema
- **WHEN** the migration is applied
- **THEN** the `user_ser_provider_configs` table exists with all four columns and a composite primary key on `(user_id, provider)`

---

### Requirement: UserSerProviderConfigRepository stores and retrieves encrypted sessions
The system SHALL define a `UserSerProviderConfigRepository` port with:
- `save(user_id: UUID, provider: str, session: SerProviderSession) -> None` — JSON-serializes and encrypts `session.data`, upserting the row for `(user_id, provider)`
- `find(user_id: UUID, provider: str) -> SerProviderSession | None` — returns the decrypted, deserialized session wrapped in a `SerProviderSession`, or `None` if none exists

#### Scenario: Save then find round-trips the session
- **WHEN** `save` is called with a `SerProviderSession` for a `(user_id, provider)` pair, followed by `find` for the same pair
- **THEN** `find` returns a `SerProviderSession` whose `data` is equal to the one originally saved

#### Scenario: find returns None when no session exists
- **WHEN** `find` is called for a `(user_id, provider)` pair with no stored row
- **THEN** the method returns `None` without raising

---

### Requirement: parking_tickets table persists created tickets
The system SHALL create a `parking_tickets` table with columns: `id UUID PRIMARY KEY`, `vehicle_id UUID NOT NULL REFERENCES vehicles(id)`, `user_id UUID NOT NULL REFERENCES users(id)`, `provider TEXT NOT NULL`, `duration_minutes INT NOT NULL`, `provider_reference TEXT`, `created_at TIMESTAMP WITH TIME ZONE NOT NULL`.

#### Scenario: parking_tickets table schema
- **WHEN** the migration is applied
- **THEN** the `parking_tickets` table exists with all seven columns, `provider_reference` nullable

---

### Requirement: ParkingTicketRepository persists ParkingTicket entities
The system SHALL define a `ParkingTicketRepository` port with `save(ticket: ParkingTicket) -> None`.

#### Scenario: Saved ticket is persisted with all fields
- **WHEN** `save` is called with a `ParkingTicket`
- **THEN** a row appears in `parking_tickets` matching all of the ticket's fields

---

### Requirement: ConnectSerTicketProvider use case provisions a user's session
The system SHALL define a `ConnectSerTicketProvider` use case with `execute(user_id: UUID, provider: str, credentials: SerProviderCredentials) -> None`, which resolves the named provider from `SerTicketProviderRegistry`, calls its `login(credentials)`, and persists the resulting session via `UserSerProviderConfigRepository.save`.

#### Scenario: Successful connection persists the session
- **WHEN** `ConnectSerTicketProvider.execute` is called with valid credentials for a registered provider
- **THEN** the provider's `login` is called with those credentials
- **THEN** the resulting session is persisted for that `(user_id, provider)` pair

#### Scenario: Unknown provider is rejected
- **WHEN** `ConnectSerTicketProvider.execute` is called with a `provider` name not present in the registry
- **THEN** the use case raises an error without calling any provider or persisting anything

---

### Requirement: CreateSerTicket use case orchestrates ticket creation
The system SHALL define a `CreateSerTicket` use case with `execute(user_id: UUID, vehicle_id: UUID, provider: str, duration_minutes: int) -> ParkingTicket`, which verifies the vehicle belongs to `user_id`, loads the stored session for `(user_id, provider)`, resolves the provider instance from the registry, calls `create_ticket(session, vehicle, duration_minutes)`, persists the returned `ParkingTicket` via `ParkingTicketRepository`, and returns it.

#### Scenario: Successful ticket creation
- **WHEN** `CreateSerTicket.execute` is called for a vehicle owned by `user_id`, with a valid stored session for `provider`
- **THEN** the provider's `create_ticket` is called with the decrypted session, the vehicle, and the duration
- **THEN** the returned `ParkingTicket` is persisted and returned to the caller

#### Scenario: Vehicle not owned by user is rejected
- **WHEN** `CreateSerTicket.execute` is called with a `vehicle_id` that does not belong to `user_id`
- **THEN** the use case raises an error without calling any provider

#### Scenario: No session found for provider is rejected
- **WHEN** `CreateSerTicket.execute` is called for a `(user_id, provider)` pair with no stored session
- **THEN** the use case raises an error without calling the provider's `create_ticket`
