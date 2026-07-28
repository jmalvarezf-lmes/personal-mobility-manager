## MODIFIED Requirements

### Requirement: GET /vehicles returns all vehicles for the authenticated user
The system SHALL expose `GET /vehicles` requiring a valid JWT session cookie. The response SHALL be a JSON array of vehicle objects, each including the vehicle's metadata and its latest known location (if any). Each object SHALL include `vehicle_id`, `brand`, `display_name`, `vin`, `license_plate`, a `location` field (null if no location recorded), and a `has_ser_tickets` boolean. Unauthenticated requests SHALL be rejected with HTTP 401.

#### Scenario: Authenticated user with vehicles
- **WHEN** an authenticated user sends `GET /vehicles`
- **THEN** the response is HTTP 200 with a JSON array containing one object per vehicle owned by that user
- **THEN** each object includes `vehicle_id`, `brand`, `display_name`, `vin`, `license_plate`, `location` (null if no location recorded), and `has_ser_tickets`

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

---

## ADDED Requirements

### Requirement: Vehicle list response includes a SER-tickets-exist flag
Each item in the `GET /vehicles` response SHALL include a `has_ser_tickets` boolean field. It SHALL be `true` if and only if at least one `ParkingTicket` exists for that vehicle, regardless of its `auto_created` value, computed via an existence check (not a full ticket fetch) so the list endpoint does not incur a per-vehicle N+1 query cost.

#### Scenario: Vehicle with at least one auto-created ticket
- **WHEN** a vehicle has one or more `ParkingTicket` rows with `auto_created=true`
- **THEN** the `has_ser_tickets` field in the list response is `true`

#### Scenario: Vehicle with only manually created tickets
- **WHEN** a vehicle has one or more `ParkingTicket` rows, all with `auto_created=false`
- **THEN** the `has_ser_tickets` field in the list response is `true`

#### Scenario: Vehicle with no tickets at all
- **WHEN** a vehicle has zero `ParkingTicket` rows
- **THEN** the `has_ser_tickets` field in the list response is `false`
