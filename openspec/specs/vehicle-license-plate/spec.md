### Requirement: Vehicle has an optional license plate field
The system SHALL support an optional `license_plate` field on the `Vehicle` domain entity. The value SHALL be a string of at most 20 characters. The field SHALL be nullable — absence of a plate is a valid and expected state for newly registered vehicles. No format or pattern validation SHALL be applied.

#### Scenario: Vehicle without a plate
- **WHEN** a vehicle has no license plate set
- **THEN** `license_plate` is `null` in all read responses

#### Scenario: Vehicle with a plate
- **WHEN** a vehicle has a license plate stored
- **THEN** `license_plate` is the stored string in all read responses

#### Scenario: License plate exceeding 20 characters is rejected
- **WHEN** a client sends a `license_plate` value longer than 20 characters on any write endpoint
- **THEN** the API returns HTTP 422

### Requirement: LicensePlate value object enforces length at the domain boundary
The domain SHALL define a `LicensePlate` frozen dataclass wrapping a `value: str`. Its `MAX_LENGTH` class constant SHALL be 20. Instantiation with a value longer than `MAX_LENGTH` SHALL raise `ValueError`.

#### Scenario: Valid plate accepted
- **WHEN** `LicensePlate("1234 ABC")` is constructed
- **THEN** no exception is raised and `plate.value == "1234 ABC"`

#### Scenario: Plate exceeding max length raises ValueError
- **WHEN** `LicensePlate("X" * 21)` is constructed
- **THEN** `ValueError` is raised

### Requirement: Vehicle repository persists and retrieves license plate
The `vehicles_table` SHALL include a nullable `license_plate` column (VARCHAR 20). The `VehicleRepository` port SHALL expose `update_license_plate(vehicle_id: UUID, license_plate: str | None) -> None`. The PostgreSQL implementation SHALL execute an `UPDATE` on `vehicles_table` setting the column to the provided value.

#### Scenario: Update sets a plate
- **WHEN** `update_license_plate(vehicle_id, "1234 ABC")` is called
- **THEN** the `license_plate` column for that vehicle is set to `"1234 ABC"`

#### Scenario: Update clears a plate
- **WHEN** `update_license_plate(vehicle_id, None)` is called
- **THEN** the `license_plate` column for that vehicle is set to `NULL`
