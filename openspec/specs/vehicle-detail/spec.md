### Requirement: GET /vehicles/{id} returns a single vehicle with role-appropriate config
The system SHALL expose `GET /vehicles/{id}` requiring a valid JWT session cookie. The response SHALL include vehicle metadata (including `license_plate`), an `is_owner` boolean, and brand-specific configuration when the caller is the owner. For sharees, the `config` field SHALL be redacted. Unauthenticated requests SHALL return HTTP 401. Requests for a vehicle neither owned by nor shared with the authenticated user SHALL return HTTP 403. Requests for a non-existent vehicle SHALL return HTTP 404.

#### Scenario: Authenticated owner retrieves Toyota vehicle
- **WHEN** an authenticated user sends `GET /vehicles/{id}` for a Toyota vehicle they own
- **THEN** the response is HTTP 200 with `vehicle_id`, `brand`, `display_name`, `vin`, `license_plate`, `is_owner: true`, and a `config` object containing `username`, `locale` and `password: "●●●●●●●●"`

#### Scenario: Authenticated owner retrieves Generic vehicle
- **WHEN** an authenticated user sends `GET /vehicles/{id}` for a Generic vehicle they own
- **THEN** the response is HTTP 200 with `vehicle_id`, `brand`, `display_name`, `license_plate`, `is_owner: true`, and a `config` object containing `location_token`

#### Scenario: Sharee retrieves vehicle with redacted config
- **WHEN** an authenticated user sends `GET /vehicles/{id}` for a vehicle shared with them
- **THEN** the response is HTTP 200 with vehicle metadata, `is_owner: false`, and a `config` object whose `redacted` field is `true`

#### Scenario: Vehicle without plate returns null in detail
- **WHEN** a vehicle has no license plate set
- **THEN** the `license_plate` field in the detail response is `null`

#### Scenario: Non-accessible vehicle receives 403
- **WHEN** an authenticated user sends `GET /vehicles/{id}` for a vehicle neither owned by nor shared with them
- **THEN** the response is HTTP 403

#### Scenario: Non-existent vehicle returns 404
- **WHEN** an authenticated user sends `GET /vehicles/{id}` with an unknown UUID
- **THEN** the response is HTTP 404

#### Scenario: Toyota password is always masked in response
- **WHEN** `GET /vehicles/{id}` is called for any Toyota vehicle by its owner
- **THEN** the `config.password` field in the response is `"●●●●●●●●"` regardless of the actual stored value
