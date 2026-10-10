## ADDED Requirements

### Requirement: Brand enum constrains valid vehicle brands
The system SHALL define `Brand` as a closed `str`-based Python enum with exactly two values: `TOYOTA` and `GENERIC`. All domain objects and API inputs that reference a brand MUST use this enum. Unknown brand strings SHALL be rejected with a 422 Unprocessable Entity response.

#### Scenario: Valid brand accepted at registration
- **WHEN** a client sends `POST /vehicles` with `brand: "toyota"` or `brand: "generic"`
- **THEN** the system accepts the request and proceeds with registration

#### Scenario: Unknown brand rejected
- **WHEN** a client sends `POST /vehicles` with an unrecognised brand string (e.g. `brand: "bmw"`)
- **THEN** the system responds with HTTP 422 and an error describing the invalid brand value

---

### Requirement: Vehicle registration creates vehicle and brand-specific config
The system SHALL expose `POST /vehicles` to register a new vehicle. The request MUST include a valid session cookie (JWT). The request body MUST include `brand`, `display_name`, and brand-specific configuration fields. On success the system SHALL create a `Vehicle` record with `owner_id` set to the authenticated user's id and a `VehicleConfig` record in the same transaction. Unauthenticated requests SHALL be rejected with HTTP 401.

#### Scenario: Register Toyota vehicle
- **WHEN** an authenticated client sends `POST /vehicles` with `brand: "toyota"`, `display_name`, `vin`, `username`, `password`, `locale`
- **THEN** the system creates a `Vehicle` row with `owner_id` set to the authenticated user's id and a `VehicleConfig` row with Toyota credentials stored AES-encrypted
- **THEN** the response contains `vehicle_id`, `brand`, `display_name`, `vin` and no credential fields

#### Scenario: Register generic vehicle
- **WHEN** an authenticated client sends `POST /vehicles` with `brand: "generic"` and `display_name`
- **THEN** the system creates a `Vehicle` row with `owner_id` set to the authenticated user's id and a `VehicleConfig` row with a generated `location_token` stored in cleartext
- **THEN** the response contains `vehicle_id`, `brand`, `display_name`, and `location_token`
- **THEN** `location_token` is a UUID-formatted opaque string

#### Scenario: Unauthenticated registration is rejected
- **WHEN** a client sends `POST /vehicles` without a session cookie or with an expired JWT
- **THEN** the system responds with HTTP 401 and no vehicle is created

---

### Requirement: Toyota credentials stored encrypted
The system SHALL store Toyota `username`, `password`, `locale`, and `vin` as a single AES-encrypted JSON blob (Fernet). The plaintext MUST never be written to the database, logs, or API responses.

#### Scenario: Toyota config payload is encrypted in DB
- **WHEN** a Toyota vehicle is registered
- **THEN** the `vehicle_configs.encrypted_payload` column contains ciphertext (not plaintext JSON)
- **THEN** no Toyota credential appears in any log line or HTTP response body

---

### Requirement: Generic location token stored in cleartext
The system SHALL store the generic `location_token` in the `vehicle_configs.location_token` column as plaintext, indexed for lookup. The token SHALL be a randomly generated UUID.

#### Scenario: Token is queryable for push dispatch
- **WHEN** a push request arrives at `POST /vehicles/{token}/location`
- **THEN** the system resolves the vehicle by querying `vehicle_configs.location_token = token` in O(1)

---

### Requirement: ENABLED_BRANDS gates vehicle registration
The system SHALL read `ENABLED_BRANDS` from the environment (comma-separated, default `generic`). Only brands listed in `ENABLED_BRANDS` SHALL be accepted at `POST /vehicles`.

#### Scenario: Default enables generic only
- **WHEN** `ENABLED_BRANDS` is not set
- **THEN** `POST /vehicles` with `brand: "generic"` succeeds
- **THEN** `POST /vehicles` with `brand: "toyota"` returns HTTP 422

#### Scenario: Toyota enabled explicitly
- **WHEN** `ENABLED_BRANDS=toyota,generic`
- **THEN** `POST /vehicles` with either brand succeeds

---

### Requirement: Vehicle repository exposes owner-scoped queries
The `VehicleRepository` port SHALL define `get_all_by_owner_id(owner_id: UUID) -> list[Vehicle]`. The `PostgresVehicleRepository` SHALL implement this method by executing a `SELECT` on `vehicles_table` filtered by `owner_id`. The previous `get_all_by_user_id` method is removed.

#### Scenario: Method exists on port
- **WHEN** `VehicleRepository` is inspected
- **THEN** `get_all_by_owner_id` is defined as an abstract method with signature `(owner_id: UUID) -> list[Vehicle]`

#### Scenario: Implementation returns only the owner's vehicles
- **WHEN** two users each have registered vehicles
- **THEN** `get_all_by_owner_id(user_a_id)` returns only vehicles whose `owner_id` equals user A's id

---

### Requirement: Vehicle entity uses owner_id
The system SHALL define the `Vehicle` domain entity with an `owner_id` field (UUID) representing the user who created the vehicle. The previous `user_id` field is renamed; the semantic meaning remains unchanged.

#### Scenario: Vehicle entity exposes owner_id
- **WHEN** a `Vehicle` entity is inspected
- **THEN** it has an `owner_id` field and no `user_id` field
