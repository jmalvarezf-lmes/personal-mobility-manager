## ADDED Requirements

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

---

### Requirement: Location history is a full time-series
The system SHALL append every location update (pull or push) as a new row in `vehicle_locations`. The `GET /vehicles/{id}/location` endpoint returns only the latest entry; no rows are overwritten or deleted by normal operation.

#### Scenario: Repeated pull updates accumulate rows
- **WHEN** the scheduler records 3 location updates for the same Toyota vehicle
- **THEN** `vehicle_locations` contains 3 rows for that vehicle with distinct `recorded_at` values
- **THEN** `GET /vehicles/{id}/location` returns the row with the most recent `recorded_at`

#### Scenario: Push updates accumulate rows
- **WHEN** an external device sends 5 push updates for the same generic vehicle
- **THEN** `vehicle_locations` contains 5 rows for that vehicle
- **THEN** `GET /vehicles/{id}/location` returns the row with the most recent `recorded_at`

---

### Requirement: Location response includes source field
The `GET /vehicles/{id}/location` response SHALL include a `source` field indicating whether the location was obtained via `pull` or `push`.

#### Scenario: Pull-sourced location tagged correctly
- **WHEN** the latest location for a Toyota vehicle was fetched by the scheduler
- **THEN** the response contains `"source": "pull"`

#### Scenario: Push-sourced location tagged correctly
- **WHEN** the latest location for a generic vehicle was sent via the push endpoint
- **THEN** the response contains `"source": "push"`

---

### Requirement: VehicleLocationRepository provides latest and history access
The system SHALL define a `VehicleLocationRepository` port with at minimum:
- `save(location: VehicleLocation) -> None`
- `get_latest(vehicle_id: UUID) -> VehicleLocation | None`
- `get_previous(vehicle_id: UUID, before: datetime) -> VehicleLocation | None` — returns the row with the greatest `recorded_at` that is strictly less than `before` for the given vehicle, or `None` if no such row exists (e.g. `before` is the vehicle's first-ever recorded location).

The `get_latest` method SHALL return the row with the greatest `recorded_at` for the given vehicle, or `None` if no rows exist.

#### Scenario: get_latest returns most recent row
- **WHEN** `vehicle_locations` contains multiple rows for a vehicle
- **THEN** `get_latest` returns the row with the highest `recorded_at`, regardless of `received_at` ordering

#### Scenario: get_previous returns the row immediately before a given timestamp
- **WHEN** `vehicle_locations` contains rows for a vehicle at three distinct `recorded_at` timestamps, and `get_previous` is called with `before` equal to the latest of the three
- **THEN** `get_previous` returns the row with the second-most-recent `recorded_at`

#### Scenario: get_previous returns None for a vehicle's first-ever location
- **WHEN** `get_previous` is called with `before` equal to the only recorded `recorded_at` for a vehicle
- **THEN** it returns `None`

---

### Requirement: Paginated location history endpoint requires authentication and owner check
The system SHALL expose `GET /vehicles/{id}/locations` that returns a page of that vehicle's recorded locations, ordered by `recorded_at` descending (newest first). The request MUST include a valid session cookie (JWT). The system SHALL verify that the authenticated user owns the requested vehicle. Unauthenticated requests SHALL be rejected with HTTP 401. Requests for a vehicle owned by a different user SHALL be rejected with HTTP 403. Requests for a non-existent vehicle SHALL be rejected with HTTP 404.

#### Scenario: Owner retrieves a page of their vehicle's location history
- **WHEN** an authenticated client sends `GET /vehicles/{id}/locations?limit=5&offset=0` for a vehicle they own with recorded locations
- **THEN** the system responds with HTTP 200 and a JSON body containing `items` (list of locations, newest first) and `has_more` (boolean)

#### Scenario: Unauthenticated request is rejected
- **WHEN** a client sends `GET /vehicles/{id}/locations` without a session cookie or with an expired JWT
- **THEN** the system responds with HTTP 401

#### Scenario: Non-owner request is rejected
- **WHEN** an authenticated client sends `GET /vehicles/{id}/locations` for a vehicle owned by a different user
- **THEN** the system responds with HTTP 403

#### Scenario: Non-existent vehicle is rejected
- **WHEN** an authenticated client sends `GET /vehicles/{id}/locations` with a non-existent `vehicle_id`
- **THEN** the system responds with HTTP 404

#### Scenario: Vehicle with no recorded locations returns an empty page
- **WHEN** an authenticated owner sends `GET /vehicles/{id}/locations` for a vehicle with no recorded locations
- **THEN** the system responds with HTTP 200 and `items: []`, `has_more: false`

---

### Requirement: Location history endpoint supports offset pagination with bounded limit
The endpoint SHALL accept `limit` (default 5, minimum 1, maximum 50) and `offset` (default 0, minimum 0) query parameters. Values outside these bounds SHALL be rejected with HTTP 422. `has_more` SHALL be `true` if and only if at least one further location exists beyond the returned page.

#### Scenario: Default pagination returns 5 items
- **WHEN** an authenticated owner sends `GET /vehicles/{id}/locations` with no query parameters for a vehicle with 8 recorded locations
- **THEN** the response contains the 5 most recent locations and `has_more: true`

#### Scenario: Second page via offset
- **WHEN** an authenticated owner sends `GET /vehicles/{id}/locations?limit=5&offset=5` for a vehicle with 8 recorded locations
- **THEN** the response contains the remaining 3 locations and `has_more: false`

#### Scenario: Limit above maximum is rejected
- **WHEN** an authenticated owner sends `GET /vehicles/{id}/locations?limit=51`
- **THEN** the system responds with HTTP 422

#### Scenario: Negative offset is rejected
- **WHEN** an authenticated owner sends `GET /vehicles/{id}/locations?offset=-1`
- **THEN** the system responds with HTTP 422

---

### Requirement: VehicleLocationRepository provides paginated history access
The `VehicleLocationRepository` port SHALL additionally define:
- `list_history(vehicle_id: UUID, limit: int, offset: int) -> tuple[list[VehicleLocation], bool]` — returns up to `limit` rows for the given vehicle ordered by `recorded_at` descending starting at `offset`, paired with a boolean indicating whether further rows exist beyond this page.

This method SHALL NOT alter the existing `save`, `get_latest`, or `get_previous` behavior.

#### Scenario: list_history returns newest-first page
- **WHEN** `vehicle_locations` contains 10 rows for a vehicle and `list_history` is called with `limit=5, offset=0`
- **THEN** it returns the 5 rows with the highest `recorded_at` values, in descending order, with the second element `True`

#### Scenario: list_history reports no further pages
- **WHEN** `vehicle_locations` contains 3 rows for a vehicle and `list_history` is called with `limit=5, offset=0`
- **THEN** it returns all 3 rows with the second element `False`

#### Scenario: list_history at an out-of-range offset returns empty
- **WHEN** `list_history` is called with `offset` greater than or equal to the vehicle's total row count
- **THEN** it returns an empty list with the second element `False`
