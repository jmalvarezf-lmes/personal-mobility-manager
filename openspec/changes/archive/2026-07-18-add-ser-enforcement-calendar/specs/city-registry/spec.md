## ADDED Requirements

### Requirement: cities database table
The system SHALL maintain a `cities` table in PostgreSQL with columns: `code` (text, primary key, e.g. `"madrid"`), `name` (text, not-null). This table is the shared reference dimension for every other city-scoped table, reusing the `city_code` values already used informally by `CityParkingDataProvider.city_code` and `provider_registry`.

#### Scenario: Table created and seeded by migration
- **WHEN** the `db-migrate` Makefile target runs
- **THEN** the `cities` table is created if it does not already exist, and contains a row with `code='madrid'`

#### Scenario: Duplicate code rejected
- **WHEN** an insert would create a second row with `code='madrid'`
- **THEN** the primary key constraint rejects it

### Requirement: cities as FK target for city-scoped tables
Every table introduced or modified by this change to carry a `city_code` column (`ser_timetable_weekday_hours`, `ser_timetable_exception`, `holidays`, `ser_zones`, `ser_zone_streets`, `ser_zone_areas`) SHALL declare a foreign key against `cities.code`.

#### Scenario: Insert with unknown city_code rejected
- **WHEN** an insert into any city-scoped table references a `city_code` with no matching row in `cities`
- **THEN** the foreign key constraint rejects it
