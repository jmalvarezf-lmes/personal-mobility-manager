## MODIFIED Requirements

### Requirement: Latest location endpoint requires authentication and vehicle access
The system SHALL expose `GET /vehicles/{id}/location` that returns the most recent `VehicleLocation` for the given vehicle. The request MUST include a valid session cookie (JWT). The system SHALL verify that the authenticated user owns or is shared on the requested vehicle. Unauthenticated requests SHALL be rejected with HTTP 401. Requests for a vehicle neither owned by nor shared with the authenticated user SHALL be rejected with HTTP 403.

#### Scenario: Owner retrieves their vehicle location
- **WHEN** an authenticated client sends `GET /vehicles/{id}/location` for a vehicle they own
- **THEN** the system responds with HTTP 200 and a JSON body containing `vehicle_id`, `lat`, `lon`, `recorded_at`, `received_at`, `source`

#### Scenario: Sharee retrieves shared vehicle location
- **WHEN** an authenticated client sends `GET /vehicles/{id}/location` for a vehicle shared with them
- **THEN** the system responds with HTTP 200 and a JSON body containing `vehicle_id`, `lat`, `lon`, `recorded_at`, `received_at`, `source`

#### Scenario: Unauthenticated request is rejected
- **WHEN** a client sends `GET /vehicles/{id}/location` without a session cookie or with an expired JWT
- **THEN** the system responds with HTTP 401

#### Scenario: Non-accessible request is rejected
- **WHEN** an authenticated client sends `GET /vehicles/{id}/location` for a vehicle neither owned by nor shared with them
- **THEN** the system responds with HTTP 403

---

### Requirement: Paginated location history endpoint requires authentication and vehicle access
The system SHALL expose `GET /vehicles/{id}/locations` that returns a page of that vehicle's recorded locations, ordered by `recorded_at` descending (newest first). The request MUST include a valid session cookie (JWT). The system SHALL verify that the authenticated user owns or is shared on the requested vehicle. Unauthenticated requests SHALL be rejected with HTTP 401. Requests for a vehicle neither owned by nor shared with the authenticated user SHALL be rejected with HTTP 403. Requests for a non-existent vehicle SHALL be rejected with HTTP 404.

#### Scenario: Owner retrieves a page of their vehicle's location history
- **WHEN** an authenticated client sends `GET /vehicles/{id}/locations?limit=5&offset=0` for a vehicle they own with recorded locations
- **THEN** the system responds with HTTP 200 and a JSON body containing `items` (list of locations, newest first) and `has_more` (boolean)

#### Scenario: Sharee retrieves shared vehicle location history
- **WHEN** an authenticated client sends `GET /vehicles/{id}/locations?limit=5&offset=0` for a vehicle shared with them with recorded locations
- **THEN** the system responds with HTTP 200 and a JSON body containing `items` and `has_more`

#### Scenario: Non-accessible request is rejected
- **WHEN** an authenticated client sends `GET /vehicles/{id}/locations` for a vehicle neither owned by nor shared with them
- **THEN** the system responds with HTTP 403
