## MODIFIED Requirements

### Requirement: SerTicketProviderPort defines login and ticket creation
The system SHALL define a `SerTicketProviderPort` abstract interface with:
- `login(credentials: SerProviderCredentials) -> SerProviderSession` — authenticates with the provider and returns a session
- `create_ticket(session: SerProviderSession, vehicle: Vehicle, duration_minutes: int, location: GeoLocation, zone: SerZone | None = None) -> ParkingTicket` — creates a parking ticket for the given vehicle, at the given location, using a previously obtained session. When `zone` is given, implementations SHALL use it directly instead of re-resolving a zone from `location` themselves — the caller has already determined the exact zone the ticket must be created for (e.g. a user-confirmed choice among ambiguous candidates) and re-resolution could disagree with that choice. When `zone` is omitted (`None`), behavior is unchanged from before this parameter existed.

#### Scenario: Port is implementation-agnostic
- **WHEN** a concrete class implements `SerTicketProviderPort`
- **THEN** it may define any internal structure for the `data` dict inside the `SerProviderCredentials` it expects and the `SerProviderSession` it returns from `login`, without changing the port's method signatures

#### Scenario: Location is always required by the port
- **WHEN** `create_ticket` is called
- **THEN** a resolved `GeoLocation` is always supplied by the caller — the port itself never falls back to a stored or default location

#### Scenario: Omitting zone preserves existing resolution behavior
- **WHEN** `create_ticket` is called without a `zone` argument
- **THEN** the implementation resolves the zone from `location` itself, exactly as it did before this parameter existed

#### Scenario: Providing zone bypasses internal resolution
- **WHEN** `create_ticket` is called with an explicit `zone`
- **THEN** the implementation uses that exact `SerZone` for the ticket, without calling its own zone-containment lookup against `location`

---

### Requirement: CreateSerTicket use case orchestrates ticket creation
The system SHALL define a `CreateSerTicket` use case with `execute(user_id: UUID, vehicle_id: UUID, provider: str, duration_minutes: int, location: GeoLocation | None = None, zone: SerZone | None = None) -> ParkingTicket`, which verifies the vehicle belongs to `user_id`, loads the stored session for `(user_id, provider)`, resolves the provider instance from the registry, resolves `location` (using the given value if provided, otherwise the vehicle's latest known location via `GetLatestVehicleLocation`), calls `create_ticket(session, vehicle, duration_minutes, location, zone=zone)`, persists the returned `ParkingTicket` via `ParkingTicketRepository`, and returns it. `zone` is passed through to the provider unchanged — `CreateSerTicket` itself never resolves or validates it.

#### Scenario: Successful ticket creation with an explicit location
- **WHEN** `CreateSerTicket.execute` is called for a vehicle owned by `user_id`, with a valid stored session for `provider` and an explicit `location`
- **THEN** the provider's `create_ticket` is called with the decrypted session, the vehicle, the duration, and that exact `location`
- **THEN** the returned `ParkingTicket` is persisted and returned to the caller

#### Scenario: Successful ticket creation falls back to the vehicle's latest known location
- **WHEN** `CreateSerTicket.execute` is called without a `location` argument, and the vehicle has a recorded location history
- **THEN** the provider's `create_ticket` is called with the vehicle's latest known `GeoLocation`

#### Scenario: An explicit zone is forwarded to the provider unchanged
- **WHEN** `CreateSerTicket.execute` is called with an explicit `zone`
- **THEN** the provider's `create_ticket` is called with that exact `zone` value

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

### Requirement: ElParkingSerTicketProvider implements ticket creation against the ElParking API
`ElParkingSerTicketProvider.create_ticket` SHALL:
1. Resolve the vehicle's ElParking `id_vehicle` by matching `vehicle.license_plate` against the authenticated user's ElParking vehicle list; raise `SerProviderVehicleNotFoundError` if no match is found.
2. Resolve the SER zone as follows: if an explicit `zone` argument was given, use it directly; otherwise resolve the SER zone containing `location` using the existing `SerZoneRepository`/`FindContainingSerZone`. ElParking is never queried for spatial containment against our own zone geometry either way.
3. Resolve `id_ser_town` for the resolved zone's `city_code` via the cached ElParking city/zone/rate mapping (see the mapping-cache requirement), matching town name case-insensitively against the `cities` table.
4. Resolve `id_ser_zone` by matching the resolved zone's `zone_number` against the cached zones' leading name number (zero-padded); when more than one cached zone matches the same `zone_number` for that town, disambiguate by testing `location` against each candidate's own polygon and selecting the containing one.
5. Resolve `id_ser_rate` by matching the resolved zone's cached rates against the zone's `zone_type` (case/accent-insensitive, ignoring a `"Tarifa "` prefix).
6. Fetch the mandatory pricing/checksum step via `ElParkingClient`, select the entry whose `stay_duration` equals `duration_minutes`, and use its `fare_qty` and the verbatim `step_request` in the final request — never constructing or altering `step_request`.
7. Submit the ticket via `ElParkingClient`, and return a `ParkingTicket` populated with the response's cost and `end_date`, and with `city_code`/`zone_number` set from the `SerZone` resolved in step 2 (no additional lookup — the same resolved zone used for id_ser_town/id_ser_zone/id_ser_rate resolution).

#### Scenario: Successful ticket creation resolves every identifier and submits the ticket
- **WHEN** `create_ticket` is called for a vehicle whose plate matches an ElParking-registered vehicle, at a location inside a known SER zone, with no explicit `zone`
- **THEN** the resulting ElParking request includes the vehicle's `id_vehicle`, the resolved `id_ser_zone`/`id_ser_rate`, the given `start_date`/`duration_minutes`, `location`'s coordinates, and the pricing step's verbatim `step_request`
- **THEN** the returned `ParkingTicket` has `cost` and `end_date` populated from ElParking's response, and `city_code`/`zone_number` populated from the zone resolved in step 2

#### Scenario: An explicit zone is used instead of re-resolving from location
- **WHEN** `create_ticket` is called with an explicit `zone` argument
- **THEN** `SerZoneRepository`/`FindContainingSerZone` is not consulted to resolve the zone — `id_ser_town`/`id_ser_zone`/`id_ser_rate` are resolved from the given `zone` directly
- **THEN** the returned `ParkingTicket`'s `city_code`/`zone_number` reflect the given `zone`, even if it differs from what `find_containing(location)` would have returned

#### Scenario: Vehicle not registered on ElParking's side raises a typed error
- **WHEN** `create_ticket` is called for a vehicle whose `license_plate` does not match any vehicle in the authenticated user's ElParking vehicle list
- **THEN** `SerProviderVehicleNotFoundError` is raised, and no further ElParking calls (town/zone/rate/steps/create) are made

#### Scenario: Duplicate zone_number within a town is disambiguated by polygon containment
- **WHEN** more than one cached ElParking zone shares the same `zone_number` for the resolved town
- **THEN** `create_ticket` selects the candidate whose own polygon contains `location`, not an arbitrary or first match
