### Requirement: GET /vehicles returns all vehicles for the authenticated user
The system SHALL expose `GET /vehicles` requiring a valid JWT session cookie. The response SHALL be a JSON array of vehicle objects, each including the vehicle's metadata and its latest known location (if any). Unauthenticated requests SHALL be rejected with HTTP 401.

#### Scenario: Authenticated user with vehicles
- **WHEN** an authenticated user sends `GET /vehicles`
- **THEN** the response is HTTP 200 with a JSON array containing one object per vehicle owned by that user
- **THEN** each object includes `vehicle_id`, `brand`, `display_name`, `vin`, and a `location` field (null if no location recorded)

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
