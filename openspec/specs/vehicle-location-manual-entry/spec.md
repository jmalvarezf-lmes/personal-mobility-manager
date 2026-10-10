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

---

### Requirement: Endpoint is restricted to generic vehicles
The system SHALL reject location submissions for non-generic vehicles, since those vehicles receive location exclusively from their own brand-specific integration.

#### Scenario: Generic vehicle accepted
- **WHEN** the target vehicle has `brand == GENERIC`
- **THEN** the location submission is processed normally

#### Scenario: Toyota vehicle rejected
- **WHEN** the target vehicle has `brand == TOYOTA`
- **THEN** the system responds with HTTP 400 and does not record a location

---

### Requirement: Submission delegates to RecordVehicleLocation use case
The endpoint SHALL resolve the vehicle and call `RecordVehicleLocation(vehicle_id, lat, lon, recorded_at, source="push")`, identical to the device-token push endpoint. It MUST NOT contain persistence logic directly.

#### Scenario: Location is persisted after submission
- **WHEN** a valid submission is received for an owned generic vehicle
- **THEN** a new row appears in `vehicle_locations` with `source="push"` and the correct `vehicle_id`
- **THEN** `received_at` is set to the server's current UTC time

---

### Requirement: Endpoint is rate-limited
The system SHALL apply two independent rate limits to `POST /vehicles/{vehicle_id}/locations`:
1. The standard `60/minute` per-remote-address limit already applied to other authenticated vehicle-mutation endpoints (`POST /vehicles`, `PUT /vehicles/{vehicle_id}`).
2. A per-vehicle limit of `1/minute`, keyed by `vehicle_id`, matching the equivalent per-token limit on the device-push endpoint — both endpoints feed the same downstream event pipeline, which has a documented sensitivity to rapid location updates near SER-zone boundaries.

#### Scenario: Excessive submission rate rejected (per-remote-address)
- **WHEN** a single remote address sends more than 60 requests per minute (across any vehicles)
- **THEN** the system responds with HTTP 429 for the excess requests

#### Scenario: Excessive submission rate rejected (per-vehicle)
- **WHEN** more than 1 submission for the same `vehicle_id` is sent within a minute
- **THEN** the system responds with HTTP 429 for the second and any further request for that vehicle within that window
