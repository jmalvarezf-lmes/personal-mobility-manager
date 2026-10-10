### Requirement: GET /vehicles returns all vehicles accessible to the authenticated user
The system SHALL expose `GET /vehicles` requiring a valid JWT session cookie. The response SHALL be a JSON array of vehicle objects, each including the vehicle's metadata, its latest known location (if any), whether it has SER tickets, and an `is_owner` boolean. The list SHALL include every vehicle owned by the authenticated user and every vehicle shared with them. Unauthenticated requests SHALL be rejected with HTTP 401.

#### Scenario: Authenticated user with owned vehicles
- **WHEN** an authenticated user sends `GET /vehicles`
- **THEN** the response is HTTP 200 with a JSON array containing one object per vehicle owned by that user, each with `is_owner: true`

#### Scenario: Authenticated user sees vehicles shared with them
- **WHEN** an authenticated user is a sharee of a vehicle owned by another user
- **THEN** the response includes that vehicle with `is_owner: false`

#### Scenario: Vehicle without plate returns null in list
- **WHEN** a vehicle has no license plate set
- **THEN** the `license_plate` field in the list item is `null`

#### Scenario: Authenticated user with no accessible vehicles
- **WHEN** an authenticated user sends `GET /vehicles` and has no owned or shared vehicles
- **THEN** the response is HTTP 200 with an empty JSON array

#### Scenario: Unauthenticated request rejected
- **WHEN** a request is sent to `GET /vehicles` without a session cookie or with an expired JWT
- **THEN** the response is HTTP 401

#### Scenario: User does not see unshared vehicles owned by others
- **WHEN** multiple users have vehicles and none are shared with the authenticated user
- **THEN** `GET /vehicles` returns only the authenticated user's owned vehicles

---

### Requirement: Vehicle list response includes latest location inline
Each item in the `GET /vehicles` response SHALL include a `location` field. If the vehicle has at least one recorded location, `location` SHALL be an object with `latitude`, `longitude`, and `recorded_at`. If no location has been recorded, `location` SHALL be `null`.

#### Scenario: Vehicle with location history
- **WHEN** a vehicle has one or more location records
- **THEN** the `location` field in the list response contains the most recent fix

#### Scenario: Vehicle with no location history
- **WHEN** a vehicle has no location records
- **THEN** the `location` field in the list response is `null`

---

### Requirement: Vehicle repository exposes list-by-user query
The `VehicleRepository` port SHALL define `get_all_by_user_id(user_id: UUID) -> list[Vehicle]`. The PostgreSQL implementation SHALL execute a `SELECT` filtered by `vehicles.user_id`.

#### Scenario: Repository returns only matching user's vehicles
- **WHEN** `get_all_by_user_id(user_a_id)` is called
- **THEN** the returned list contains only vehicles whose `user_id` equals `user_a_id`

---

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

## ADDED Requirements

### Requirement: Vehicle list response includes ownership flag
Each item in the `GET /vehicles` response SHALL include an `is_owner` boolean field. It SHALL be `true` if and only if the authenticated user is the vehicle's `owner_id`.

#### Scenario: Owned vehicle marks is_owner true
- **WHEN** a list item represents a vehicle owned by the authenticated user
- **THEN** the item contains `is_owner: true`

#### Scenario: Shared vehicle marks is_owner false
- **WHEN** a list item represents a vehicle shared with the authenticated user
- **THEN** the item contains `is_owner: false`
