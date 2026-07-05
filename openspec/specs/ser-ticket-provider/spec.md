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

---

### Requirement: SerProviderAuthenticationError and SerProviderApiError define the port's failure contract
The system SHALL define `SerProviderAuthenticationError` (raised when a provider rejects credentials as invalid) and `SerProviderApiError` (raised for any other provider-side failure: network errors, rate limiting, unexpected/malformed responses) as domain exceptions, following the existing `class XError(Exception): pass` convention.

#### Scenario: Authentication failure is distinguishable from other failures
- **WHEN** a `SerTicketProviderPort.login` implementation cannot authenticate due to invalid credentials
- **THEN** it raises `SerProviderAuthenticationError`, not `SerProviderApiError` or a generic exception

#### Scenario: Non-authentication failures are distinguishable
- **WHEN** a `SerTicketProviderPort.login` implementation fails for any reason other than credential rejection (network failure, unexpected response, rate limiting)
- **THEN** it raises `SerProviderApiError`

---

### Requirement: ElParkingSerTicketProvider implements login against the ElParking API
The system SHALL provide `ElParkingSerTicketProvider`, an implementation of `SerTicketProviderPort`, whose `login` method calls ElParking's `POST /v1/logins` endpoint with `email`/`password` (and `uid`/`model` if present) from `credentials.data`, using header `ep-app-name: elparking` (hardcoded) and header `ep-app-version` sourced from the `ELPARKING_APP_VERSION` environment variable (default: `"26.2"`), since the app version is expected to evolve over time. On success, it SHALL return a `SerProviderSession` whose `data` contains exactly `access_token` (str) and `device_session_id` (int, from the response's `id` field) — no other fields from the response.

#### Scenario: ep-app-version defaults to 26.2
- **WHEN** `login` is called and `ELPARKING_APP_VERSION` is not set
- **THEN** the request to ElParking includes header `ep-app-version: 26.2`

#### Scenario: ep-app-version is configurable
- **WHEN** `ELPARKING_APP_VERSION` is set to a different value
- **THEN** the request to ElParking includes that value as `ep-app-version`, not the default

#### Scenario: Successful login returns a minimal session
- **WHEN** `login` is called with valid ElParking credentials and the API returns a 2xx response with `access_token` and `id`
- **THEN** the returned `SerProviderSession.data` contains exactly `{"access_token": <value>, "device_session_id": <value>}`

#### Scenario: Invalid credentials raise SerProviderAuthenticationError
- **WHEN** `login` is called with credentials ElParking rejects as invalid
- **THEN** `SerProviderAuthenticationError` is raised and no session is returned

#### Scenario: Unexpected API failure raises SerProviderApiError
- **WHEN** the ElParking API is unreachable, returns a 5xx or 429 response, or an unexpected response shape
- **THEN** `SerProviderApiError` is raised, and no raw `httpx` exception propagates out of the provider

---

### Requirement: ElParkingSerTicketProvider.create_ticket is an explicit not-yet-implemented stub
The system SHALL have `ElParkingSerTicketProvider.create_ticket` raise `NotImplementedError` with a message indicating ticket creation is not yet implemented for this provider.

#### Scenario: create_ticket is called before it exists
- **WHEN** `ElParkingSerTicketProvider.create_ticket` is called
- **THEN** it raises `NotImplementedError`, and no HTTP call to ElParking is made

---

### Requirement: SerTicketProviderRegistry registers ElParking when enabled
`SerTicketProviderRegistry.build_providers()` SHALL include `ElParkingSerTicketProvider` under the key `"elparking"` when `"elparking"` appears in the comma-separated `ENABLED_SER_PROVIDERS` environment variable (default: `"elparking"`, i.e. enabled unless explicitly overridden). If `"elparking"` is enabled but `ENCRYPTION_KEY` is not set, the system SHALL raise `RuntimeError` at startup — this SHALL NOT be deferred to the first connection attempt.

#### Scenario: ElParking is registered by default
- **WHEN** `ENABLED_SER_PROVIDERS` is not set and the registry is built with `ENCRYPTION_KEY` present
- **THEN** the returned mapping contains `"elparking"` bound to an `ElParkingSerTicketProvider` instance

#### Scenario: ElParking can be disabled
- **WHEN** `ENABLED_SER_PROVIDERS` is set to a value that does not include `"elparking"` (e.g. `""`)
- **THEN** the returned mapping does not contain `"elparking"`

#### Scenario: Missing encryption key fails fast at startup
- **WHEN** `"elparking"` is enabled via `ENABLED_SER_PROVIDERS` but `ENCRYPTION_KEY` is not set
- **THEN** building the registry raises `RuntimeError` immediately, before any user can attempt to connect an account

---

### Requirement: SerTicketProviderConnectFactory builds provider-specific credentials
The system SHALL provide `SerTicketProviderConnectFactory` in the presentation layer, which builds a `SerProviderCredentials` from a validated connect-request body and the current user's id. For ElParking, the resulting `credentials.data` SHALL include `email`, `password`, `uid` (set to `str(user_id)`), and `model` (a fixed string identifying this backend as a server integration).

#### Scenario: Factory injects a stable, non-random uid
- **WHEN** the factory builds `SerProviderCredentials` for an ElParking connect request from user `user_id`
- **THEN** `credentials.data["uid"]` equals `str(user_id)`, not a randomly generated value

---

### Requirement: Authenticated user can create a SER provider connection over HTTP
The system SHALL expose `POST /ser-ticket-providers/connections`, requiring an authenticated session, accepting a discriminated request body (`provider` field selects the shape, e.g. `ConnectElParkingRequest` for `provider: "elparking"` with `email` and `password`). On success, it calls `ConnectSerTicketProvider.execute` for the current user and returns `204 No Content`. `SerProviderAuthenticationError` SHALL map to `401 Unauthorized`; `SerProviderApiError` SHALL map to `502 Bad Gateway`; `SerTicketProviderNotFoundError` (unknown/disabled provider) SHALL map to `404 Not Found`.

#### Scenario: Successful connection
- **WHEN** an authenticated user submits valid ElParking credentials to `POST /ser-ticket-providers/connections`
- **THEN** the response is `204 No Content`
- **THEN** a session is persisted for that user and `"elparking"`

#### Scenario: Invalid credentials surface as 401
- **WHEN** an authenticated user submits credentials ElParking rejects
- **THEN** the response is `401 Unauthorized`, and no session is persisted

#### Scenario: Provider-side failure surfaces as 502
- **WHEN** the ElParking API is unreachable or returns an unexpected failure during a connection attempt
- **THEN** the response is `502 Bad Gateway`, and no session is persisted

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie is sent to `POST /ser-ticket-providers/connections`
- **THEN** the response is `401 Unauthorized` and no provider is contacted
