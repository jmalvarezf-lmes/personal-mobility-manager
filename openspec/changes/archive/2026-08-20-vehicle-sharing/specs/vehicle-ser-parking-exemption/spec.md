## MODIFIED Requirements

### Requirement: GET /vehicles/{id}/ser-parking-exemptions returns the vehicle's exemption
The system SHALL expose `GET /vehicles/{id}/ser-parking-exemptions` requiring a valid JWT session cookie. Unauthenticated requests SHALL return HTTP 401. Requests for a vehicle neither owned by nor shared with the authenticated user SHALL return HTTP 403. Requests for a non-existent vehicle SHALL return HTTP 404. When the vehicle exists and is accessible to the caller, the response SHALL be HTTP 200 with `{ "city_code": ..., "zone_number": ... }` if an exemption exists, or `{ "city_code": null, "zone_number": null }` if none is set.

#### Scenario: Owner retrieves an existing exemption
- **WHEN** an authenticated owner sends `GET /vehicles/{id}/ser-parking-exemptions` for a vehicle with a stored exemption
- **THEN** the response is HTTP 200 with the stored `city_code` and `zone_number`

#### Scenario: Sharee retrieves an existing exemption
- **WHEN** an authenticated sharee sends `GET /vehicles/{id}/ser-parking-exemptions` for a shared vehicle with a stored exemption
- **THEN** the response is HTTP 200 with the stored `city_code` and `zone_number`

#### Scenario: Owner retrieves when no exemption is set
- **WHEN** an authenticated owner sends `GET /vehicles/{id}/ser-parking-exemptions` for a vehicle with no exemption row
- **THEN** the response is HTTP 200 with `city_code: null` and `zone_number: null`

#### Scenario: Non-accessible vehicle receives 403
- **WHEN** an authenticated user sends `GET /vehicles/{id}/ser-parking-exemptions` for a vehicle neither owned by nor shared with them
- **THEN** the response is HTTP 403

---

### Requirement: POST /vehicles/{id}/ser-parking-exemptions sets or replaces the vehicle's exemption
The system SHALL expose `POST /vehicles/{id}/ser-parking-exemptions` requiring a valid JWT session cookie. The endpoint SHALL be restricted to the vehicle's owner. Unauthenticated requests SHALL return HTTP 401. Requests from a sharee or other non-owner SHALL return HTTP 403. Requests for a non-existent vehicle SHALL return HTTP 404.

#### Scenario: Owner sets a new exemption
- **WHEN** an authenticated owner sends `POST /vehicles/{id}/ser-parking-exemptions` with a valid `city_code` and `zone_number`
- **THEN** a new row is created and the response is HTTP 200 with the stored `city_code` and `zone_number`

#### Scenario: Sharee set rejected
- **WHEN** an authenticated sharee sends `POST /vehicles/{id}/ser-parking-exemptions`
- **THEN** the response is HTTP 403

---

### Requirement: DELETE /vehicles/{id}/ser-parking-exemptions clears the vehicle's exemption
The system SHALL expose `DELETE /vehicles/{id}/ser-parking-exemptions` requiring a valid JWT session cookie. The endpoint SHALL be restricted to the vehicle's owner. Unauthenticated requests SHALL return HTTP 401. Requests from a sharee or other non-owner SHALL return HTTP 403. Requests for a non-existent vehicle SHALL return HTTP 404. On success the system SHALL delete any existing exemption row and return HTTP 204.

#### Scenario: Owner clears an existing exemption
- **WHEN** an authenticated owner sends `DELETE /vehicles/{id}/ser-parking-exemptions` for a vehicle with a stored exemption
- **THEN** the row is deleted and the response is HTTP 204

#### Scenario: Sharee delete rejected
- **WHEN** an authenticated sharee sends `DELETE /vehicles/{id}/ser-parking-exemptions`
- **THEN** the response is HTTP 403
