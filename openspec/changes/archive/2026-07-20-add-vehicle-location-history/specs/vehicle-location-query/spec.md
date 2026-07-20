## ADDED Requirements

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
