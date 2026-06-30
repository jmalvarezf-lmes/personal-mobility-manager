## MODIFIED Requirements

### Requirement: Vehicle registration creates vehicle and brand-specific config
The system SHALL expose `POST /vehicles` to register a new vehicle. The request MUST include a valid session cookie (JWT). The request body MUST include `brand`, `display_name`, and brand-specific configuration fields. On success the system SHALL create a `Vehicle` record (with `user_id` from the JWT) and a `VehicleConfig` record in the same transaction. Unauthenticated requests SHALL be rejected with HTTP 401.

#### Scenario: Register Toyota vehicle
- **WHEN** an authenticated client sends `POST /vehicles` with `brand: "toyota"`, `display_name`, `vin`, `username`, `password`, `locale`
- **THEN** the system creates a `Vehicle` row (with `user_id` set to the authenticated user's id) and a `VehicleConfig` row with Toyota credentials stored AES-encrypted
- **THEN** the response contains `vehicle_id`, `brand`, `display_name`, `vin` and no credential fields

#### Scenario: Register generic vehicle
- **WHEN** an authenticated client sends `POST /vehicles` with `brand: "generic"` and `display_name`
- **THEN** the system creates a `Vehicle` row (with `user_id` set to the authenticated user's id) and a `VehicleConfig` row with a generated `location_token` stored in cleartext
- **THEN** the response contains `vehicle_id`, `brand`, `display_name`, and `location_token`
- **THEN** `location_token` is a UUID-formatted opaque string

#### Scenario: Unauthenticated registration is rejected
- **WHEN** a client sends `POST /vehicles` without a session cookie or with an expired JWT
- **THEN** the system responds with HTTP 401 and no vehicle is created

#### Scenario: Registration rejected for disabled brand
- **WHEN** an authenticated client attempts to register a vehicle whose brand is not listed in `ENABLED_BRANDS`
- **THEN** the system responds with HTTP 422 and a message indicating the brand is not enabled
