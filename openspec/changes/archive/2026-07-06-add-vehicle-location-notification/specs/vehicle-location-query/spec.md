## MODIFIED Requirements

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
