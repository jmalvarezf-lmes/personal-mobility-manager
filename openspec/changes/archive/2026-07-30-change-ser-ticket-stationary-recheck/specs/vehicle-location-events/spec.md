## MODIFIED Requirements

### Requirement: RecordVehicleLocation publishes VehicleLocationUpdated after every valid call
The system SHALL have `RecordVehicleLocation.execute` publish a `VehicleLocationUpdated` event via the injected `EventPublisher` for every call whose coordinates and timestamp pass validation, for both `source="pull"` and `source="push"` calls — including when the coordinates are identical to the vehicle's last stored location. Persistence and publication SHALL be independent: `RecordVehicleLocation` SHALL skip writing a new `VehicleLocation` row when the coordinates exactly match the vehicle's last stored location (avoiding a redundant duplicate row), but SHALL still construct and publish a `VehicleLocationUpdated` event in that case, with a freshly-computed `received_at` reflecting the current call, not the time of the originally-stored fix.

#### Scenario: Event published after successful pull ingestion
- **WHEN** the scheduler successfully records a pulled location
- **THEN** a `VehicleLocationUpdated` event with `source="pull"` is published

#### Scenario: Event published after successful push ingestion
- **WHEN** the push endpoint successfully records a pushed location
- **THEN** a `VehicleLocationUpdated` event with `source="push"` is published

#### Scenario: No event published on validation failure
- **WHEN** `RecordVehicleLocation.execute` raises `ValueError` due to invalid coordinates or timestamp
- **THEN** no event is published, since the location was never persisted

#### Scenario: Unchanged coordinates still publish an event, without a duplicate row
- **WHEN** `RecordVehicleLocation.execute` is called with coordinates identical to the vehicle's last stored location
- **THEN** no new `VehicleLocation` row is persisted
- **THEN** a `VehicleLocationUpdated` event is still published, carrying the unchanged coordinates and a `received_at` reflecting the time of this call
