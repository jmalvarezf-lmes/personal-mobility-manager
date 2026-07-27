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
The system SHALL apply two independent rate limits to `POST /vehicles/{token}/location`:
1. The existing per-remote-address limit of `60/minute` (unchanged, shared with the `api-rate-limiting` capability's other endpoints) — guards against abuse from a single source hammering many different vehicle tokens.
2. A new per-vehicle-token limit of `1/minute`, keyed by the `token` path parameter rather than the caller's IP address — added after a 4R review of the `ser-ticket-auto-creation` capability found that, combined with GPS jitter near a SER zone boundary, a single vehicle pushing locations faster than this could retrigger `SerTicketCreationTriggerHandler`'s zone-transition gate (and, in a failure edge case, repeated real ticket-creation attempts against the SER provider) far more often than intended. Capping how often a single vehicle's own location can be updated bounds this independently of GPS noise or the gate's own floor.

Both limits are enforced independently; either being exceeded SHALL result in HTTP 429 for the excess request.

#### Scenario: Excessive push rate rejected (per-remote-address)
- **WHEN** a single remote address sends more than 60 push requests per minute (across any tokens)
- **THEN** the system responds with HTTP 429 for the excess requests

#### Scenario: Excessive push rate rejected (per-vehicle-token)
- **WHEN** a single token is used for more than 1 push request within a minute
- **THEN** the system responds with HTTP 429 for the second and any further request for that same token within that window, regardless of the remote address making the request

#### Scenario: Two different tokens are rate-limited independently
- **WHEN** two different vehicle tokens each push a location within the same one-minute window
- **THEN** neither push is rejected on account of the other — the per-token limit tracks each token's own request count separately
