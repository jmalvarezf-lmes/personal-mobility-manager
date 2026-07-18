## MODIFIED Requirements

### Requirement: Upsert SER zone data into PostgreSQL
The system SHALL store parsed zone boundary records in PostgreSQL using a delete-and-reload strategy scoped to the ingesting provider's `city_code`, within a single transaction, across three tables: `ser_zones` (fields `city_code`, `zone_number`, `zone_type`, `district`, `spot_count`, `geometry_wkt`), `ser_zone_streets` (one row per `(city_code, zone_number, zone_type, street_name)` tuple), and `ser_zone_areas` (one row per resolvable `(city_code, zone_number)`, holding its Barrios-shapefile-derived frontier geometry and neighbourhood name — see the `ser-zone-frontier` capability).

#### Scenario: Successful ingestion run
- **WHEN** parsing and joining completes with at least one valid zone boundary record for a given `city_code`
- **THEN** the system deletes existing `ser_zones`, `ser_zone_streets`, and `ser_zone_areas` rows matching that `city_code` only, and bulk-inserts all valid records (tagged with that `city_code`) into all three tables in a single transaction, then commits

#### Scenario: Ingesting one city does not affect another city's stored data
- **WHEN** an ingestion run completes for `city_code="madrid"`
- **THEN** rows belonging to any other `city_code` already stored in `ser_zones`, `ser_zone_streets`, or `ser_zone_areas` are left unchanged

#### Scenario: Partial failure rolls back
- **WHEN** an error occurs during bulk insert into any of the three tables
- **THEN** the transaction is rolled back and the previous data in all three tables (across all cities) remains unchanged

#### Scenario: Ingestion run logs summary
- **WHEN** an ingestion run completes (success or failure)
- **THEN** the system logs: `city_code`, total bands downloaded, bands parsed, bands skipped, zone boundary records inserted, and elapsed time

#### Scenario: Zero parsed records aborts the run
- **WHEN** parsing and joining completes with zero valid zone boundary records for a given `city_code` (not a download/HTTP failure, but a successful fetch that yields no usable data)
- **THEN** the system aborts the run without deleting or modifying that city's rows in `ser_zones`/`ser_zone_streets`/`ser_zone_areas`, logs an error, and the failure propagates the same way a download failure would

#### Scenario: Zero resolved zone areas while records is non-empty also aborts the run
- **WHEN** `get_records()` returns a non-empty list but `get_zone_areas()` returns an empty list for a given `city_code` (e.g. the Barrios shapefile fetch degraded to zero usable records)
- **THEN** the system aborts the run without deleting or modifying that city's rows in any of the three tables, logs an error, and does not silently leave `ser_zone_areas` empty while `ser_zones`/`ser_zone_streets` update

### Requirement: ser_zones database table
The system SHALL maintain a `ser_zones` table in PostgreSQL with columns: `id` (serial PK), `city_code` (text, not-null, references `cities.code`), `zone_number` (varchar(10), not-null), `zone_type` (varchar(50), not-null), `district` (text, not-null), `spot_count` (integer, not-null, default -1), `geometry_wkt` (text, not-null, WKT in EPSG:25830). A `UNIQUE (city_code, zone_number, zone_type)` constraint SHALL exist. `spot_count = -1` is the sentinel for unknown spot count. Street names are NOT stored on this table — see the `ser_zone_streets` requirement below. Pre-existing rows SHALL be backfilled to `city_code='madrid'` in the same migration that adds the column.

#### Scenario: Table created by migration
- **WHEN** the `db-migrate` Makefile target runs
- **THEN** the `ser_zones` table, its `city_code` foreign key, and its widened unique constraint are created if they do not already exist

#### Scenario: Existing rows backfilled on migration
- **WHEN** the `city_code`-adding migration runs against a database with pre-existing `ser_zones` rows
- **THEN** every existing row has `city_code` set to `'madrid'`, and no row is left with a `NULL` `city_code`

#### Scenario: Geometry stored in UTM metres
- **WHEN** a zone boundary record is inserted
- **THEN** `geometry_wkt` contains a valid WKT `POLYGON` or `MULTIPOLYGON` in EPSG:25830 coordinates

#### Scenario: Duplicate city_code, zone_number, and zone_type rejected
- **WHEN** an insert would create a second row with the same `(city_code, zone_number, zone_type)` triple within one ingestion transaction
- **THEN** the unique constraint prevents it (the ingestion pipeline dissolves bands before insert, so this should not occur in practice)

#### Scenario: Same zone_number reused across two different cities is allowed
- **WHEN** two rows share the same `zone_number` and `zone_type` but have different `city_code` values
- **THEN** both rows are accepted, since the unique constraint is scoped by `city_code`

### Requirement: ser_zone_streets database table
The system SHALL maintain a `ser_zone_streets` table in PostgreSQL with columns: `id` (serial PK), `city_code` (text, not-null, references `cities.code`), `zone_number` (varchar(10), not-null), `zone_type` (varchar(50), not-null), `street_name` (text, not-null), with an index on `(city_code, zone_number, zone_type)`. Each row associates one street name with one zone; a zone spanning multiple streets has multiple rows. Pre-existing rows SHALL be backfilled to `city_code='madrid'` in the same migration that adds the column.

#### Scenario: Table created by migration
- **WHEN** the `db-migrate` Makefile target runs
- **THEN** the `ser_zone_streets` table and its widened index are created if they do not already exist

#### Scenario: Existing rows backfilled on migration
- **WHEN** the `city_code`-adding migration runs against a database with pre-existing `ser_zone_streets` rows
- **THEN** every existing row has `city_code` set to `'madrid'`

#### Scenario: Zone with multiple streets has multiple rows
- **WHEN** a `SerZoneBoundaryRecord` with three distinct `street_names` is inserted
- **THEN** three rows are inserted into `ser_zone_streets`, all sharing that record's `city_code`, `zone_number`, and `zone_type`
