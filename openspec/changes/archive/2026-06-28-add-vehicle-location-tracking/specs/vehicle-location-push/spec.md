## ADDED Requirements

### Requirement: Push endpoint accepts location from generic vehicles
The system SHALL expose `POST /vehicles/{token}/location` to accept a GPS location update from an external device. The endpoint SHALL accept `lat`, `lon`, and `recorded_at` in the request body. No authentication header is required — possession of the `token` is the authorization.

#### Scenario: Valid push accepted
- **WHEN** a client sends `POST /vehicles/{token}/location` with valid `lat`, `lon`, `recorded_at`
- **THEN** the system resolves the vehicle by token, stores the location with `source="push"`, and responds with HTTP 204

#### Scenario: Invalid lat/lon rejected
- **WHEN** `lat` is outside [-90, 90] or `lon` is outside [-180, 180]
- **THEN** the system responds with HTTP 422 and a validation error

#### Scenario: `recorded_at` in the future rejected
- **WHEN** `recorded_at` is more than 60 seconds in the future relative to server time
- **THEN** the system responds with HTTP 422 indicating the timestamp is invalid

---

### Requirement: Unknown token returns 404
The system SHALL return HTTP 404 when no vehicle config matches the provided token. The response MUST NOT distinguish between "token does not exist" and "vehicle is disabled" to avoid information leakage.

#### Scenario: Token not found
- **WHEN** a client sends a push request with a token that does not match any `vehicle_configs.location_token`
- **THEN** the system responds with HTTP 404

---

### Requirement: Push endpoint URL is unique per vehicle
Each registered generic vehicle SHALL have a distinct `location_token`. The endpoint `POST /vehicles/{token}/location` is effectively unique per vehicle — sharing the token with a third party grants that party the ability to submit location updates for that vehicle only.

#### Scenario: Two generic vehicles have distinct tokens
- **WHEN** two generic vehicles are registered independently
- **THEN** each has a different `location_token`
- **THEN** a push to vehicle A's token does not affect vehicle B's location history

---

### Requirement: Push ingest delegates to RecordVehicleLocation use case
The push endpoint SHALL resolve the vehicle from the token and call `RecordVehicleLocation(vehicle_id, lat, lon, recorded_at, source="push")`. It MUST NOT contain persistence logic directly.

#### Scenario: Location is persisted after push
- **WHEN** a valid push request is received
- **THEN** a new row appears in `vehicle_locations` with `source="push"` and the correct `vehicle_id`
- **THEN** `received_at` is set to the server's current UTC time

---

### Requirement: Push endpoint rate-limited
The system SHALL apply rate limiting to `POST /vehicles/{token}/location` to prevent abuse. The limit SHALL be configurable via the existing SlowAPI limiter.

#### Scenario: Excessive push rate rejected
- **WHEN** a single token sends more push requests per minute than the configured limit
- **THEN** the system responds with HTTP 429 for the excess requests
