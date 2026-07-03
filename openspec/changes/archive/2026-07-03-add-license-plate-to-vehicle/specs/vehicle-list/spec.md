## MODIFIED Requirements

### Requirement: GET /vehicles returns all vehicles for the authenticated user
The system SHALL expose `GET /vehicles` requiring a valid JWT session cookie. The response SHALL be a JSON array of vehicle objects, each including the vehicle's metadata and its latest known location (if any). Each object SHALL include `vehicle_id`, `brand`, `display_name`, `vin`, `license_plate`, and a `location` field (null if no location recorded). Unauthenticated requests SHALL be rejected with HTTP 401.

#### Scenario: Authenticated user with vehicles
- **WHEN** an authenticated user sends `GET /vehicles`
- **THEN** the response is HTTP 200 with a JSON array containing one object per vehicle owned by that user
- **THEN** each object includes `vehicle_id`, `brand`, `display_name`, `vin`, `license_plate`, and a `location` field (null if no location recorded)

#### Scenario: Vehicle without a plate returns null in list
- **WHEN** a vehicle has no license plate set
- **THEN** the `license_plate` field in the list item is `null`

#### Scenario: Vehicle with a plate returns the value in list
- **WHEN** a vehicle has a license plate stored
- **THEN** the `license_plate` field in the list item is the stored string

#### Scenario: Authenticated user with no vehicles
- **WHEN** an authenticated user sends `GET /vehicles` and has no registered vehicles
- **THEN** the response is HTTP 200 with an empty JSON array

#### Scenario: Unauthenticated request rejected
- **WHEN** a request is sent to `GET /vehicles` without a session cookie or with an expired JWT
- **THEN** the response is HTTP 401

#### Scenario: User only sees own vehicles
- **WHEN** multiple users have vehicles registered
- **THEN** `GET /vehicles` for user A returns only user A's vehicles, never user B's
