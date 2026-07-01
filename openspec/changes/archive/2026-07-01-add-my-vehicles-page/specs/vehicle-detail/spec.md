## ADDED Requirements

### Requirement: GET /vehicles/{id} returns a single vehicle with masked config
The system SHALL expose `GET /vehicles/{id}` requiring a valid JWT session cookie. The response SHALL include vehicle metadata and brand-specific configuration. Toyota passwords SHALL be masked (returned as the string `"●●●●●●●●"`). Unauthenticated requests SHALL return HTTP 401. Requests for a vehicle not owned by the authenticated user SHALL return HTTP 403. Requests for a non-existent vehicle SHALL return HTTP 404.

#### Scenario: Authenticated owner retrieves Toyota vehicle
- **WHEN** an authenticated user sends `GET /vehicles/{id}` for a Toyota vehicle they own
- **THEN** the response is HTTP 200 with `vehicle_id`, `brand`, `display_name`, `vin`, and a `config` object containing `username`, `locale` and `password: "●●●●●●●●"`

#### Scenario: Authenticated owner retrieves Generic vehicle
- **WHEN** an authenticated user sends `GET /vehicles/{id}` for a Generic vehicle they own
- **THEN** the response is HTTP 200 with `vehicle_id`, `brand`, `display_name` and a `config` object containing `location_token`

#### Scenario: Non-owner receives 403
- **WHEN** an authenticated user sends `GET /vehicles/{id}` for a vehicle owned by a different user
- **THEN** the response is HTTP 403

#### Scenario: Non-existent vehicle returns 404
- **WHEN** an authenticated user sends `GET /vehicles/{id}` with an unknown UUID
- **THEN** the response is HTTP 404

#### Scenario: Toyota password is always masked in response
- **WHEN** `GET /vehicles/{id}` is called for any Toyota vehicle
- **THEN** the `config.password` field in the response is `"●●●●●●●●"` regardless of the actual stored value
