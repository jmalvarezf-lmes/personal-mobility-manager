### Requirement: ParkingTicket entity represents a created SER ticket
The system SHALL define a `ParkingTicket` domain entity with fields: `id` (UUID), `vehicle_id` (UUID), `user_id` (UUID), `provider` (str), `duration_minutes` (int), `provider_reference` (str or None), `cost` (float), `end_date` (datetime), `created_at` (datetime).

#### Scenario: ParkingTicket entity is immutable value object
- **WHEN** a `ParkingTicket` is constructed
- **THEN** it is a frozen dataclass (or equivalent) with all eight fields populated (`provider_reference` may be `None`)

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
- `create_ticket(session: SerProviderSession, vehicle: Vehicle, duration_minutes: int, location: GeoLocation) -> ParkingTicket` — creates a parking ticket for the given vehicle, at the given location, using a previously obtained session

#### Scenario: Port is implementation-agnostic
- **WHEN** a concrete class implements `SerTicketProviderPort`
- **THEN** it may define any internal structure for the `data` dict inside the `SerProviderCredentials` it expects and the `SerProviderSession` it returns from `login`, without changing the port's method signatures

#### Scenario: Location is always required by the port
- **WHEN** `create_ticket` is called
- **THEN** a resolved `GeoLocation` is always supplied by the caller — the port itself never falls back to a stored or default location

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
The system SHALL define a `CreateSerTicket` use case with `execute(user_id: UUID, vehicle_id: UUID, provider: str, duration_minutes: int, location: GeoLocation | None = None) -> ParkingTicket`, which verifies the vehicle belongs to `user_id`, loads the stored session for `(user_id, provider)`, resolves the provider instance from the registry, resolves `location` (using the given value if provided, otherwise the vehicle's latest known location via `GetLatestVehicleLocation`), calls `create_ticket(session, vehicle, duration_minutes, location)`, persists the returned `ParkingTicket` via `ParkingTicketRepository`, and returns it.

#### Scenario: Successful ticket creation with an explicit location
- **WHEN** `CreateSerTicket.execute` is called for a vehicle owned by `user_id`, with a valid stored session for `provider` and an explicit `location`
- **THEN** the provider's `create_ticket` is called with the decrypted session, the vehicle, the duration, and that exact `location`
- **THEN** the returned `ParkingTicket` is persisted and returned to the caller

#### Scenario: Successful ticket creation falls back to the vehicle's latest known location
- **WHEN** `CreateSerTicket.execute` is called without a `location` argument, and the vehicle has a recorded location history
- **THEN** the provider's `create_ticket` is called with the vehicle's latest known `GeoLocation`

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

---

### Requirement: SerTicketProviderPort defines a logout method
The system SHALL extend `SerTicketProviderPort` with an abstract `logout(self, session: SerProviderSession) -> None` method, invalidating the provider-side session. Implementations that raise for any failure SHALL raise `SerProviderApiError`, consistent with `login`'s existing failure vocabulary.

#### Scenario: Provider implements logout
- **WHEN** a concrete `SerTicketProviderPort` implementation is asked to log out a valid session
- **THEN** it invalidates that session on the provider's side and returns without error

#### Scenario: Logout failure raises SerProviderApiError
- **WHEN** a provider's logout call fails (network error, unexpected response)
- **THEN** it raises `SerProviderApiError`, not a generic or provider-specific exception

---

### Requirement: ElParkingSerTicketProvider implements logout
`ElParkingSerTicketProvider.logout` SHALL call ElParking's `DELETE /v1/logins/{access_token}` (using the `access_token` from `session.data`), authenticating with HTTP Basic auth using a blank username and `access_token` as the password — not an `Authorization: Bearer` header.

#### Scenario: Successful logout calls ElParking's revoke endpoint
- **WHEN** `logout` is called with a valid session
- **THEN** a `DELETE` request is sent to `{base_url}/v1/logins/{access_token}` authenticated with HTTP Basic auth (blank username, `access_token` as password)

#### Scenario: Logout failure is wrapped
- **WHEN** ElParking's logout endpoint is unreachable or returns an unexpected status
- **THEN** `SerProviderApiError` is raised and no raw `httpx` exception propagates

---

### Requirement: UserSerProviderConfigRepository supports deletion and listing
The system SHALL extend `UserSerProviderConfigRepository` with:
- `delete(user_id: UUID, provider: str) -> None` — removes the stored session for `(user_id, provider)`, if present. SHALL NOT raise if no such row exists (idempotent).
- `list_connected_providers(user_id: UUID) -> list[str]` — returns the provider names for which `user_id` has a stored session.

#### Scenario: Delete removes an existing session
- **WHEN** `delete` is called for a `(user_id, provider)` pair with a stored session
- **THEN** a subsequent `find` for the same pair returns `None`

#### Scenario: Delete is idempotent
- **WHEN** `delete` is called for a `(user_id, provider)` pair with no stored session
- **THEN** it completes without raising

#### Scenario: list_connected_providers reflects stored sessions
- **WHEN** a user has stored sessions for `"elparking"` and no other provider
- **THEN** `list_connected_providers` returns `["elparking"]`

#### Scenario: list_connected_providers returns empty for a user with no connections
- **WHEN** a user has no stored SER provider sessions
- **THEN** `list_connected_providers` returns an empty list

---

### Requirement: DisconnectSerTicketProvider use case removes a connection with best-effort logout
The system SHALL define `DisconnectSerTicketProvider` with `execute(user_id: UUID, provider: str) -> bool`, returning whether the provider-side logout succeeded. It SHALL:
- Return `True` immediately if no session exists for `(user_id, provider)` (idempotent success).
- Attempt `provider.logout(session)` via the registered provider instance if one is available; treat a missing/unregistered provider instance as a logout failure, not an error.
- Catch `SerProviderApiError` from `logout` without propagating it.
- Always call `UserSerProviderConfigRepository.delete(user_id, provider)`, regardless of whether logout succeeded.

#### Scenario: Full disconnect when logout succeeds
- **WHEN** `execute` is called for a connected user and the provider's logout succeeds
- **THEN** it returns `True`
- **THEN** the local session is deleted

#### Scenario: Disconnect completes even when logout fails
- **WHEN** `execute` is called for a connected user and the provider's logout raises `SerProviderApiError`
- **THEN** it returns `False`
- **THEN** the local session is still deleted

#### Scenario: Disconnect completes when the provider is unregistered
- **WHEN** `execute` is called for a provider that is not currently registered (e.g. disabled via configuration since the user connected)
- **THEN** it returns `False`
- **THEN** the local session is still deleted

#### Scenario: Disconnecting an already-disconnected provider is a no-op success
- **WHEN** `execute` is called for a `(user_id, provider)` pair with no stored session
- **THEN** it returns `True` without attempting to contact any provider

---

### Requirement: ListSerTicketProviderConnections use case reports connected providers
The system SHALL define a use case with `execute(user_id: UUID) -> list[str]`, returning `UserSerProviderConfigRepository.list_connected_providers(user_id)`.

#### Scenario: Reports currently connected providers
- **WHEN** `execute` is called for a user with a stored ElParking session
- **THEN** it returns `["elparking"]`

---

### Requirement: Authenticated user can list their SER provider connections
The system SHALL expose `GET /ser-ticket-providers/connections`, requiring an authenticated session, returning `{"providers": [<provider names>]}` for the current user.

#### Scenario: Returns connected providers
- **WHEN** an authenticated user with a connected ElParking account calls `GET /ser-ticket-providers/connections`
- **THEN** the response is `200 OK` with `{"providers": ["elparking"]}`

#### Scenario: Returns an empty list when nothing is connected
- **WHEN** an authenticated user with no connections calls `GET /ser-ticket-providers/connections`
- **THEN** the response is `200 OK` with `{"providers": []}`

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie is sent to `GET /ser-ticket-providers/connections`
- **THEN** the response is `401 Unauthorized`

---

### Requirement: Authenticated user can disconnect a SER provider connection
The system SHALL expose `DELETE /ser-ticket-providers/connections/{provider}`, requiring an authenticated session, calling `DisconnectSerTicketProvider.execute` for the current user and the path's `provider`. It SHALL respond `200 OK` with `{"logout_succeeded": <bool>}` — never `204`, since the body must carry the soft-failure signal.

#### Scenario: Successful disconnect with confirmed logout
- **WHEN** an authenticated user disconnects a provider and the provider-side logout succeeds
- **THEN** the response is `200 OK` with `{"logout_succeeded": true}`
- **THEN** a subsequent `GET /ser-ticket-providers/connections` no longer lists that provider

#### Scenario: Disconnect succeeds locally even if logout could not be confirmed
- **WHEN** an authenticated user disconnects a provider and the provider-side logout fails
- **THEN** the response is `200 OK` with `{"logout_succeeded": false}`
- **THEN** a subsequent `GET /ser-ticket-providers/connections` no longer lists that provider

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie is sent to `DELETE /ser-ticket-providers/connections/{provider}`
- **THEN** the response is `401 Unauthorized` and no provider is contacted

---

### Requirement: SER Providers page lets a user connect, view, and disconnect provider accounts
The system SHALL provide a frontend "SER Providers" page, reachable only via a protected route, listing known SER ticket providers (ElParking today) with their connection status, a way to connect (submitting credentials via a modal), and a way to disconnect an existing connection. If a disconnect's `logout_succeeded` is `false`, the page SHALL inform the user without treating the disconnect as failed.

#### Scenario: Logged-out user cannot reach the SER Providers page
- **WHEN** an unauthenticated visitor navigates to the SER Providers route
- **THEN** they are redirected away, consistent with other protected routes

#### Scenario: Connecting a provider updates its displayed status
- **WHEN** a logged-in user submits valid credentials for a not-yet-connected provider
- **THEN** the page reflects that provider as connected without requiring a manual refresh

#### Scenario: Disconnecting shows a soft warning on unconfirmed logout
- **WHEN** a logged-in user disconnects a provider and the response indicates `logout_succeeded: false`
- **THEN** the page shows the provider as disconnected
- **THEN** the page also displays a non-blocking message noting the provider-side logout could not be confirmed

---

### Requirement: SER Providers page shows a provider icon
Each provider row on the SER Providers page SHALL display an icon sourced from a locally-hosted static asset (`/provider-logos/{provider}.webp`), never hotlinked from a third-party URL. If the asset is unavailable, the row SHALL render without the icon rather than showing a broken-image placeholder — this is a purely presentational concern, unrelated to the API, domain model, or stored data.

#### Scenario: Icon renders when the asset exists
- **WHEN** a provider row is displayed and its logo asset exists at the expected local path
- **THEN** the icon is shown alongside the provider's name

#### Scenario: Missing icon degrades gracefully
- **WHEN** a provider row is displayed and its logo asset does not exist or fails to load
- **THEN** the row still renders fully (name, status, action button), without a broken-image indicator

---

### Requirement: Logged-in navigation includes a SER Providers entry
The system SHALL add a "SER Providers" link to the existing account dropdown menu, alongside My Vehicles, Preferences, and Logout.

#### Scenario: Logged-in user sees the SER Providers entry
- **WHEN** an authenticated user opens the account dropdown
- **THEN** it includes a link to the SER Providers page, alongside the existing entries

---

### Requirement: ElParkingClient centralizes ElParking HTTP calls with correct authentication
The system SHALL provide `ElParkingClient`, an infrastructure helper wrapping every ElParking HTTP call (`login`, `logout`, list the user's vehicles, list SER towns, list a town's zones, fetch pricing/checksum steps, create a ticket). Every authenticated call (all except `login`) SHALL authenticate with HTTP Basic auth using a blank username and the session's `access_token` as the password, and SHALL include the `ep-app-name`/`ep-app-version` headers used by `login`.

#### Scenario: Authenticated calls use HTTP Basic auth, not Bearer
- **WHEN** `ElParkingClient` makes any authenticated call other than `login`
- **THEN** the request is sent with HTTP Basic auth (blank username, `access_token` as password), and no `Authorization: Bearer` header is sent

#### Scenario: Authenticated calls include the required app headers
- **WHEN** `ElParkingClient` makes any authenticated call
- **THEN** the request includes `ep-app-name` and `ep-app-version` headers with the same values `login` sends

---

### Requirement: ElParkingSerTicketProvider implements ticket creation against the ElParking API
`ElParkingSerTicketProvider.create_ticket` SHALL:
1. Resolve the vehicle's ElParking `id_vehicle` by matching `vehicle.license_plate` against the authenticated user's ElParking vehicle list; raise `SerProviderVehicleNotFoundError` if no match is found.
2. Resolve the SER zone containing `location` using the existing `SerZoneRepository`/`FindContainingSerZone` — ElParking is never queried for spatial containment against our own zone geometry.
3. Resolve `id_ser_town` for the zone's `city_code` via the cached ElParking city/zone/rate mapping (see the mapping-cache requirement), matching town name case-insensitively against the `cities` table.
4. Resolve `id_ser_zone` by matching the zone's `zone_number` against the cached zones' leading name number (zero-padded); when more than one cached zone matches the same `zone_number` for that town, disambiguate by testing `location` against each candidate's own polygon and selecting the containing one.
5. Resolve `id_ser_rate` by matching the resolved zone's cached rates against the zone's `zone_type` (case/accent-insensitive, ignoring a `"Tarifa "` prefix).
6. Fetch the mandatory pricing/checksum step via `ElParkingClient`, select the entry whose `stay_duration` equals `duration_minutes`, and use its `fare_qty` and the verbatim `step_request` in the final request — never constructing or altering `step_request`.
7. Submit the ticket via `ElParkingClient`, and return a `ParkingTicket` populated with the response's cost and `end_date`.

#### Scenario: Successful ticket creation resolves every identifier and submits the ticket
- **WHEN** `create_ticket` is called for a vehicle whose plate matches an ElParking-registered vehicle, at a location inside a known SER zone
- **THEN** the resulting ElParking request includes the vehicle's `id_vehicle`, the resolved `id_ser_zone`/`id_ser_rate`, the given `start_date`/`duration_minutes`, `location`'s coordinates, and the pricing step's verbatim `step_request`
- **THEN** the returned `ParkingTicket` has `cost` and `end_date` populated from ElParking's response

#### Scenario: Vehicle not registered on ElParking's side raises a typed error
- **WHEN** `create_ticket` is called for a vehicle whose `license_plate` does not match any vehicle in the authenticated user's ElParking vehicle list
- **THEN** `SerProviderVehicleNotFoundError` is raised, and no further ElParking calls (town/zone/rate/steps/create) are made

#### Scenario: Duplicate zone_number within a town is disambiguated by polygon containment
- **WHEN** more than one cached ElParking zone shares the same `zone_number` for the resolved town
- **THEN** `create_ticket` selects the candidate whose own polygon contains `location`, not an arbitrary or first match

---

### Requirement: ElParking zone-mapping cache resolves city/zone/rate identifiers
The system SHALL cache ElParking's town/zone/rate identifiers per `(city_code, provider)`, populated by calling `ElParkingClient`'s town/zone listing using whichever session is available at the time of a cache miss. A cached entry SHALL be considered fresh for 30 days from when it was fetched; a request for a `(city_code, provider)` pair with no cached entry, or one older than 30 days, SHALL trigger a fresh fetch before resolution proceeds. This cache is infrastructure-internal: no domain or application-layer code SHALL reference ElParking-specific identifiers (`id_ser_town`, `id_ser_zone`, `id_ser_rate`).

#### Scenario: Cache miss triggers a fetch
- **WHEN** ticket creation needs the mapping for a `(city_code, provider)` pair with no cached entry
- **THEN** `ElParkingClient`'s town/zone listing is called using the current request's session, and the result is cached before resolution continues

#### Scenario: Fresh cache entry is reused without a new fetch
- **WHEN** ticket creation needs the mapping for a `(city_code, provider)` pair with a cached entry fetched fewer than 30 days ago
- **THEN** no ElParking town/zone listing call is made; the cached data is used directly

#### Scenario: Stale cache entry triggers a refresh
- **WHEN** ticket creation needs the mapping for a `(city_code, provider)` pair with a cached entry fetched 30 or more days ago
- **THEN** a fresh fetch is performed and the cache is updated before resolution continues

---

### Requirement: SerProviderVehicleNotFoundError signals an unmatched vehicle
The system SHALL define `SerProviderVehicleNotFoundError` as a domain exception, raised when a vehicle's license plate cannot be matched against a SER ticket provider's own vehicle records, following the existing `class XError(Exception): pass` convention.

#### Scenario: Distinguishable from other provider failures
- **WHEN** a `SerTicketProviderPort.create_ticket` implementation cannot match the given vehicle against the provider's own vehicle records
- **THEN** it raises `SerProviderVehicleNotFoundError`, not `SerProviderApiError` or a generic exception

---

### Requirement: VehicleNotPresentInSerTicketProvider domain event
The system SHALL define a `VehicleNotPresentInSerTicketProvider` frozen domain event with fields `vehicle_id` (UUID), `user_id` (UUID), `provider` (str), published via the existing `EventPublisher` port by `CreateSerTicket` when the provider raises `SerProviderVehicleNotFoundError`. No subscriber is registered for this event in this change.

#### Scenario: Event is published on vehicle-not-found
- **WHEN** `CreateSerTicket.execute` catches `SerProviderVehicleNotFoundError` from the provider
- **THEN** it publishes a `VehicleNotPresentInSerTicketProvider` event with the request's `vehicle_id`, `user_id`, and `provider`

#### Scenario: No handler is required to exist yet
- **WHEN** `VehicleNotPresentInSerTicketProvider` is published and no handler is subscribed
- **THEN** publishing succeeds without error, exactly as `InMemoryEventPublisher` already behaves for events with zero subscribers

---

### Requirement: Authenticated user can create a SER ticket over HTTP
The system SHALL expose `POST /parking/ser-tickets`, requiring an authenticated session, accepting `{"vehicle_id": UUID, "provider": str, "duration_minutes": int, "latitude": float | None, "longitude": float | None}`. When both `latitude` and `longitude` are given, they SHALL be used as an explicit location override; when either is omitted, the vehicle's latest known location SHALL be used. On success, it SHALL call `CreateSerTicket.execute` for the current user and return `201 Created` with the created ticket's `id`, `cost`, `end_date`, and `provider_reference`. `VehicleNotFoundError` SHALL map to `404 Not Found`; `SerProviderSessionNotFoundError` SHALL map to `404 Not Found`; `SerProviderVehicleNotFoundError` SHALL map to `409 Conflict`; `SerProviderApiError` SHALL map to `502 Bad Gateway`.

#### Scenario: Successful creation with an explicit location
- **WHEN** an authenticated user submits `vehicle_id`, `provider`, `duration_minutes`, `latitude`, and `longitude` for an owned vehicle with a connected provider session
- **THEN** the response is `201 Created` with the ticket's `id`, `cost`, `end_date`, and `provider_reference`

#### Scenario: Successful creation without an explicit location
- **WHEN** an authenticated user submits `vehicle_id`, `provider`, and `duration_minutes` only, and the vehicle has a recorded location history
- **THEN** the ticket is created using the vehicle's latest known location, and the response is `201 Created`

#### Scenario: Vehicle not present on the provider's side surfaces as 409
- **WHEN** the requested vehicle's license plate cannot be matched against the provider's own vehicle records
- **THEN** the response is `409 Conflict`

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie is sent to `POST /parking/ser-tickets`
- **THEN** the response is `401 Unauthorized` and no provider is contacted
