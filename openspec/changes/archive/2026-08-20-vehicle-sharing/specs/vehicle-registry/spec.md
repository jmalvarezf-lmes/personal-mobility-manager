## MODIFIED Requirements

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

### Requirement: Vehicle entity uses owner_id
The system SHALL define the `Vehicle` domain entity with an `owner_id` field (UUID) representing the user who created the vehicle. The previous `user_id` field is renamed; the semantic meaning remains unchanged.

#### Scenario: Vehicle entity exposes owner_id
- **WHEN** a `Vehicle` entity is inspected
- **THEN** it has an `owner_id` field and no `user_id` field

---

### Requirement: Vehicle repository exposes owner-scoped queries
The `VehicleRepository` port SHALL define `get_all_by_owner_id(owner_id: UUID) -> list[Vehicle]`. The `PostgresVehicleRepository` SHALL implement this method by executing a `SELECT` on `vehicles_table` filtered by `owner_id`. The previous `get_all_by_user_id` method is removed.

#### Scenario: Method exists on port
- **WHEN** `VehicleRepository` is inspected
- **THEN** `get_all_by_owner_id` is defined as an abstract method with signature `(owner_id: UUID) -> list[Vehicle]`

#### Scenario: Implementation returns only the owner's vehicles
- **WHEN** two users each have registered vehicles
- **THEN** `get_all_by_owner_id(user_a_id)` returns only vehicles whose `owner_id` equals user A's id
