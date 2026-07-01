## ADDED Requirements

### Requirement: ON DELETE CASCADE on vehicle child table foreign keys
A new Alembic migration SHALL alter the `vehicle_configs.vehicle_id` and `vehicle_locations.vehicle_id` foreign key constraints to add `ON DELETE CASCADE`. After this migration, deleting a row from `vehicles` SHALL automatically delete all associated rows in `vehicle_configs` and `vehicle_locations`.

#### Scenario: Deleting a vehicle cascades to vehicle_configs
- **WHEN** a vehicle row is deleted from the `vehicles` table
- **THEN** the corresponding `vehicle_configs` row (if any) is automatically deleted

#### Scenario: Deleting a vehicle cascades to vehicle_locations
- **WHEN** a vehicle row is deleted from the `vehicles` table
- **THEN** all `vehicle_locations` rows with that `vehicle_id` are automatically deleted

#### Scenario: Migration is reversible
- **WHEN** `alembic downgrade -1` is executed after applying the cascade migration
- **THEN** the foreign key constraints revert to their previous state (no cascade) without error

#### Scenario: Existing rows are not affected
- **WHEN** the cascade migration is applied to a database with existing vehicles, configs, and locations
- **THEN** all existing rows are preserved unchanged; only the FK constraint definition changes
