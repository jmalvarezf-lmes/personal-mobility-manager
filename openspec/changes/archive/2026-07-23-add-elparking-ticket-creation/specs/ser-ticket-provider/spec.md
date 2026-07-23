## MODIFIED Requirements

### Requirement: ParkingTicket entity represents a created SER ticket
The system SHALL define a `ParkingTicket` domain entity with fields: `id` (UUID), `vehicle_id` (UUID), `user_id` (UUID), `provider` (str), `duration_minutes` (int), `provider_reference` (str or None), `cost` (float), `end_date` (datetime), `created_at` (datetime).

#### Scenario: ParkingTicket entity is immutable value object
- **WHEN** a `ParkingTicket` is constructed
- **THEN** it is a frozen dataclass (or equivalent) with all eight fields populated (`provider_reference` may be `None`)

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

### Requirement: ElParkingSerTicketProvider implements logout
`ElParkingSerTicketProvider.logout` SHALL call ElParking's `DELETE /v1/logins/{access_token}` (using the `access_token` from `session.data`), authenticating with HTTP Basic auth using a blank username and `access_token` as the password — not an `Authorization: Bearer` header.

#### Scenario: Successful logout calls ElParking's revoke endpoint
- **WHEN** `logout` is called with a valid session
- **THEN** a `DELETE` request is sent to `{base_url}/v1/logins/{access_token}` authenticated with HTTP Basic auth (blank username, `access_token` as password)

#### Scenario: Logout failure is wrapped
- **WHEN** ElParking's logout endpoint is unreachable or returns an unexpected status
- **THEN** `SerProviderApiError` is raised and no raw `httpx` exception propagates

## ADDED Requirements

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

## REMOVED Requirements

### Requirement: ElParkingSerTicketProvider.create_ticket is an explicit not-yet-implemented stub
**Reason**: Superseded by a real implementation now that ElParking's ticket-creation API contract is known.
**Migration**: See "ElParkingSerTicketProvider implements ticket creation against the ElParking API" above.
