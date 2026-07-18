## MODIFIED Requirements

### Requirement: ser_zone_areas database table
The system SHALL maintain a `ser_zone_areas` table in PostgreSQL with columns: `city_code` (text, not-null, references `cities.code`), `zone_number` (varchar(10)), `neighbourhood` (text, not-null), `geometry_wkt` (text, not-null, WKT in EPSG:25830), with primary key `(city_code, zone_number)`. This table is keyed by `(city_code, zone_number)` — both the frontier geometry and the neighbourhood name are zone_number-scoped concepts within a city, independent of `zone_type`. Pre-existing rows SHALL be backfilled to `city_code='madrid'` in the same migration that adds the column.

#### Scenario: Table created by migration
- **WHEN** the `db-migrate` Makefile target runs
- **THEN** the `ser_zone_areas` table with its composite primary key is created if it does not already exist

#### Scenario: Existing rows backfilled on migration
- **WHEN** the `city_code`-adding migration runs against a database with pre-existing `ser_zone_areas` rows
- **THEN** every existing row has `city_code` set to `'madrid'`, and the widened primary key accepts all backfilled rows without collision

#### Scenario: One row per zone_number regardless of colour count
- **WHEN** a zone_number has three `ser_zones` rows (one per colour: Azul, Verde, Alta Rotación) within the same city
- **THEN** `ser_zone_areas` still has exactly one row for that `(city_code, zone_number)`

#### Scenario: Same zone_number reused across two different cities is allowed
- **WHEN** two rows share the same `zone_number` but have different `city_code` values
- **THEN** both rows are accepted, since the primary key is scoped by `city_code`
