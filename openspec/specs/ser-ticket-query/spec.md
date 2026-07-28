### Requirement: Paginated SER ticket list endpoint requires authentication and owner check
The system SHALL expose `GET /vehicles/{vehicle_id}/ser-tickets` that returns a page of the given vehicle's `ParkingTicket` rows — every ticket regardless of `auto_created` — ordered by `created_at` descending (newest first). The request MUST include a valid session cookie (JWT). The system SHALL verify that the authenticated user owns the requested vehicle. Unauthenticated requests SHALL be rejected with HTTP 401. Requests for a vehicle owned by a different user SHALL be rejected with HTTP 403. Requests for a non-existent vehicle SHALL be rejected with HTTP 404.

#### Scenario: Owner retrieves a page of their vehicle's SER tickets
- **WHEN** an authenticated client sends `GET /vehicles/{vehicle_id}/ser-tickets?limit=5&offset=0` for a vehicle they own with recorded tickets
- **THEN** the system responds with HTTP 200 and a JSON body containing `items` (list of tickets, newest first) and `has_more` (boolean)

#### Scenario: Both auto-created and manually created tickets are returned
- **WHEN** an authenticated owner sends `GET /vehicles/{vehicle_id}/ser-tickets` for a vehicle with both `auto_created=true` and `auto_created=false` tickets
- **THEN** the response `items` include tickets of both kinds

#### Scenario: Unauthenticated request is rejected
- **WHEN** a client sends `GET /vehicles/{vehicle_id}/ser-tickets` without a session cookie or with an expired JWT
- **THEN** the system responds with HTTP 401

#### Scenario: Non-owner request is rejected
- **WHEN** an authenticated client sends `GET /vehicles/{vehicle_id}/ser-tickets` for a vehicle owned by a different user
- **THEN** the system responds with HTTP 403

#### Scenario: Non-existent vehicle is rejected
- **WHEN** an authenticated client sends `GET /vehicles/{vehicle_id}/ser-tickets` with a non-existent `vehicle_id`
- **THEN** the system responds with HTTP 404

#### Scenario: Vehicle with no tickets returns an empty page
- **WHEN** an authenticated owner sends `GET /vehicles/{vehicle_id}/ser-tickets` for a vehicle with zero `ParkingTicket` rows
- **THEN** the system responds with HTTP 200 and `items: []`, `has_more: false`

---

### Requirement: SER ticket list endpoint supports offset pagination with bounded limit
The endpoint SHALL accept `limit` (default 5, minimum 1, maximum 50) and `offset` (default 0, minimum 0) query parameters, matching the convention of `GET /vehicles/{id}/locations`. Values outside these bounds SHALL be rejected with HTTP 422. `has_more` SHALL be `true` if and only if at least one further ticket exists for the vehicle beyond the returned page.

#### Scenario: Default pagination returns 5 items
- **WHEN** an authenticated owner sends `GET /vehicles/{vehicle_id}/ser-tickets` with no query parameters for a vehicle with 8 tickets
- **THEN** the response contains the 5 most recent tickets and `has_more: true`

#### Scenario: Second page via offset
- **WHEN** an authenticated owner sends `GET /vehicles/{vehicle_id}/ser-tickets?limit=5&offset=5` for a vehicle with 8 tickets
- **THEN** the response contains the remaining 3 tickets and `has_more: false`

#### Scenario: Limit above maximum is rejected
- **WHEN** an authenticated owner sends `GET /vehicles/{vehicle_id}/ser-tickets?limit=51`
- **THEN** the system responds with HTTP 422

#### Scenario: Negative offset is rejected
- **WHEN** an authenticated owner sends `GET /vehicles/{vehicle_id}/ser-tickets?offset=-1`
- **THEN** the system responds with HTTP 422

---

### Requirement: Ticket list item includes resolved city name, zone, coordinates, both dates, and creation provenance
Each item in the `GET /vehicles/{vehicle_id}/ser-tickets` response SHALL include: `id`, `latitude` (nullable), `longitude` (nullable), `start_date` (the ticket's `created_at`), `end_date`, `city_code`, `city_name` (resolved from `city_code` via the existing cities lookup; `null` if `city_code` is `null` or has no matching city), `zone_number`, and `auto_created` (nullable boolean — `null` for tickets persisted before this field existed).

#### Scenario: Ticket with a known city code resolves a display name
- **WHEN** a listed ticket has `city_code="MAD"` and the cities lookup has a city with that code named "Madrid"
- **THEN** the item's `city_name` is `"Madrid"`

#### Scenario: Ticket with no city code has a null city name
- **WHEN** a listed ticket has `city_code=null`
- **THEN** the item's `city_name` is `null`

#### Scenario: start_date reflects ticket creation time
- **WHEN** a listed ticket was persisted with `created_at` equal to a given instant
- **THEN** the item's `start_date` equals that instant

#### Scenario: Auto-created ticket is flagged
- **WHEN** a listed ticket has `auto_created=true`
- **THEN** the item's `auto_created` field is `true`

#### Scenario: Manually created ticket is flagged
- **WHEN** a listed ticket has `auto_created=false`
- **THEN** the item's `auto_created` field is `false`

#### Scenario: Pre-existing ticket has unknown provenance
- **WHEN** a listed ticket was persisted before `auto_created` existed (`auto_created=null`)
- **THEN** the item's `auto_created` field is `null`

---

### Requirement: ParkingTicketRepository provides paginated, vehicle-scoped listing of all tickets
The `ParkingTicketRepository` port SHALL additionally define `list_by_vehicle(vehicle_id: UUID, limit: int, offset: int) -> tuple[list[ParkingTicket], bool]` — returns up to `limit` rows for the given vehicle, regardless of `auto_created`, ordered by `created_at` descending starting at `offset`, paired with a boolean indicating whether further rows exist beyond this page. This method SHALL NOT alter the existing `save` behavior.

#### Scenario: list_by_vehicle returns every ticket regardless of auto_created
- **WHEN** a vehicle has 3 tickets with `auto_created=true` and 2 with `auto_created=false`, and `list_by_vehicle(vehicle_id, limit=10, offset=0)` is called
- **THEN** it returns all 5 tickets

#### Scenario: list_by_vehicle returns newest-first page
- **WHEN** a vehicle has 10 tickets and `list_by_vehicle` is called with `limit=5, offset=0`
- **THEN** it returns the 5 rows with the highest `created_at` values, in descending order, with the second element `True`

#### Scenario: list_by_vehicle reports no further pages
- **WHEN** a vehicle has 3 tickets and `list_by_vehicle` is called with `limit=5, offset=0`
- **THEN** it returns all 3 rows with the second element `False`

---

### Requirement: ListSerTickets use case orchestrates the paginated listing
The system SHALL define a `ListSerTickets` use case with `execute(vehicle_id: UUID, limit: int, offset: int) -> tuple[list[ParkingTicket], bool]`, which calls `ParkingTicketRepository.list_by_vehicle(vehicle_id, limit=limit, offset=offset)` and returns its result unchanged. Ownership verification is performed by the router dependency (`require_owned_vehicle`), not by this use case.

#### Scenario: Use case delegates directly to the repository
- **WHEN** `ListSerTickets.execute(vehicle_id, limit=5, offset=0)` is called
- **THEN** `ParkingTicketRepository.list_by_vehicle` is called with the same `vehicle_id`, `limit`, `offset`
</content>
