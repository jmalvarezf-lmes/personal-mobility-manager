## MODIFIED Requirements

### Requirement: Latest location endpoint requires authentication and owner check
The system SHALL expose `GET /vehicles/{id}/location` that returns the most recent `VehicleLocation` for the given vehicle. The request MUST include a valid session cookie (JWT). The system SHALL verify that the authenticated user owns the requested vehicle. Unauthenticated requests SHALL be rejected with HTTP 401. Requests for a vehicle owned by a different user SHALL be rejected with HTTP 403.

#### Scenario: Owner retrieves their vehicle location
- **WHEN** an authenticated client sends `GET /vehicles/{id}/location` for a vehicle they own
- **THEN** the system responds with HTTP 200 and a JSON body containing `vehicle_id`, `lat`, `lon`, `recorded_at`, `received_at`, `source`

#### Scenario: Unauthenticated request is rejected
- **WHEN** a client sends `GET /vehicles/{id}/location` without a session cookie or with an expired JWT
- **THEN** the system responds with HTTP 401

#### Scenario: Non-owner request is rejected
- **WHEN** an authenticated client sends `GET /vehicles/{id}/location` for a vehicle owned by a different user
- **THEN** the system responds with HTTP 403

#### Scenario: Vehicle has no location history
- **WHEN** an authenticated owner sends `GET /vehicles/{id}/location` for their vehicle with no recorded locations
- **THEN** the system responds with HTTP 404 and a message indicating no location is available yet

#### Scenario: Vehicle does not exist
- **WHEN** an authenticated client sends `GET /vehicles/{id}/location` with a non-existent `vehicle_id`
- **THEN** the system responds with HTTP 404
