## MODIFIED Requirements

### Requirement: Authenticated endpoint accepts location from the vehicle's owner
The system SHALL expose `POST /vehicles/{vehicle_id}/locations` (plural) to accept a GPS location update from the authenticated owner of that vehicle. The endpoint SHALL require a valid user session and SHALL accept `lat`, `lon`, and `recorded_at` in the request body, using the same validation rules as `POST /vehicles/{token}/location`.

#### Scenario: Valid submission accepted
- **WHEN** the authenticated owner of a generic vehicle sends `POST /vehicles/{vehicle_id}/locations` with valid `lat`, `lon`, `recorded_at`
- **THEN** the system stores the location with `source="push"` and responds with HTTP 204

#### Scenario: Sharee submission rejected
- **WHEN** an authenticated sharee sends `POST /vehicles/{vehicle_id}/locations` for a shared generic vehicle
- **THEN** the system responds with HTTP 403 and does not record a location

#### Scenario: Unauthenticated request rejected
- **WHEN** a request is sent without a valid user session
- **THEN** the system responds with HTTP 401

---

### Requirement: Endpoint is scoped to the vehicle's owner
The system SHALL resolve the target vehicle using the same ownership-check dependency as other authenticated vehicle-mutation endpoints (`PUT /vehicles/{vehicle_id}`). A user MUST NOT be able to submit a location for a vehicle they do not own.

#### Scenario: Owner submits successfully
- **WHEN** the authenticated user owns the target vehicle
- **THEN** the request is processed normally

#### Scenario: Non-owner request rejected
- **WHEN** the authenticated user does not own the vehicle identified by `vehicle_id`
- **THEN** the system responds with HTTP 403

#### Scenario: Unknown vehicle rejected
- **WHEN** `vehicle_id` does not match any existing vehicle
- **THEN** the system responds with HTTP 404
