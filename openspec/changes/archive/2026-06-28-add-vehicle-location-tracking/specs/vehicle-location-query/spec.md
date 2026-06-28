## ADDED Requirements

### Requirement: Latest location endpoint returns most recent known position
The system SHALL expose `GET /vehicles/{id}/location` that returns the most recent `VehicleLocation` for the given vehicle, ordered by `recorded_at` descending.

#### Scenario: Vehicle has location history
- **WHEN** a client sends `GET /vehicles/{id}/location` for a vehicle with at least one recorded location
- **THEN** the system responds with HTTP 200 and a JSON body containing `vehicle_id`, `lat`, `lon`, `recorded_at`, `received_at`, `source`

#### Scenario: Vehicle has no location history
- **WHEN** a client sends `GET /vehicles/{id}/location` for a vehicle with no recorded locations
- **THEN** the system responds with HTTP 404 and a message indicating no location is available yet

#### Scenario: Vehicle does not exist
- **WHEN** a client sends `GET /vehicles/{id}/location` with a non-existent `vehicle_id`
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

The `get_latest` method SHALL return the row with the greatest `recorded_at` for the given vehicle, or `None` if no rows exist.

#### Scenario: get_latest returns most recent row
- **WHEN** `vehicle_locations` contains multiple rows for a vehicle
- **THEN** `get_latest` returns the row with the highest `recorded_at`, regardless of `received_at` ordering
