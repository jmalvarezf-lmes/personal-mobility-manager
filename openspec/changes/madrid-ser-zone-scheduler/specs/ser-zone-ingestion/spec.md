## ADDED Requirements

### Requirement: Download Madrid callejero CSV
The system SHALL download the Madrid callejero dataset from a configurable URL (`MADRID_CALLEJERO_URL` env var) via HTTP on each scheduled ingestion run.

#### Scenario: Successful download
- **WHEN** the scheduler triggers an ingestion run and the URL is reachable
- **THEN** the system downloads the CSV file into memory (streamed) without writing a temp file

#### Scenario: Download failure
- **WHEN** the HTTP request returns a non-2xx status or a network error occurs
- **THEN** the system logs an error with the status code and skips the ingestion run, leaving existing data intact

#### Scenario: Configurable URL
- **WHEN** the env var `MADRID_CALLEJERO_URL` is set
- **THEN** the system uses that URL instead of the default

---

### Requirement: Parse SER zone fields from CSV
The system SHALL parse each CSV row and extract: street name, SER zone code, UTM X coordinate, and UTM Y coordinate. Rows missing any of these four fields SHALL be skipped with a warning log.

#### Scenario: Valid row parsed
- **WHEN** a CSV row contains all four required fields in the expected columns
- **THEN** the system produces a `SerZoneRecord` with street name, zone code, and ETRS89 UTM coordinates

#### Scenario: Row with missing SER zone skipped
- **WHEN** a CSV row has an empty or null SER zone code field
- **THEN** the system skips that row and increments a skipped-row counter

#### Scenario: Column names used for field lookup
- **WHEN** the CSV column order changes but column header names remain the same
- **THEN** the system still parses correctly without code changes

---

### Requirement: Reproject coordinates to WGS84
The system SHALL reproject UTM ETRS89 Zone 30N (EPSG:25830) coordinates to WGS84 (EPSG:4326) latitude/longitude during ingestion.

#### Scenario: Valid UTM coordinates reprojected
- **WHEN** a row contains valid UTM X/Y values in EPSG:25830
- **THEN** the system produces a WGS84 lat/lng pair within the bounding box of the Community of Madrid (lat 39.8–41.2, lng -4.6–-2.9)

#### Scenario: Invalid coordinate values skipped
- **WHEN** a row contains non-numeric or out-of-range coordinate values
- **THEN** the system skips that row with a warning log

---

### Requirement: Upsert SER zone data into PostgreSQL
The system SHALL store parsed records in the `ser_zones` PostgreSQL table using a truncate-and-reload strategy within a single transaction.

#### Scenario: Successful ingestion run
- **WHEN** parsing completes with at least one valid record
- **THEN** the system truncates `ser_zones` and bulk-inserts all valid records in a single transaction, then commits

#### Scenario: Partial failure rolls back
- **WHEN** an error occurs during bulk insert
- **THEN** the transaction is rolled back and the previous data remains unchanged

#### Scenario: Ingestion run logs summary
- **WHEN** an ingestion run completes (success or failure)
- **THEN** the system logs: total rows downloaded, rows parsed, rows skipped, rows inserted, and elapsed time

---

### Requirement: Scheduled periodic ingestion
The system SHALL run ingestion automatically on a configurable interval (default: every 24 hours), starting at application startup.

#### Scenario: Scheduler starts on app boot
- **WHEN** the FastAPI application starts
- **THEN** the APScheduler `BackgroundScheduler` starts and schedules the ingestion job with the configured interval

#### Scenario: Configurable interval
- **WHEN** the env var `INGESTION_INTERVAL_HOURS` is set to a positive integer
- **THEN** the scheduler uses that interval instead of the 24-hour default

#### Scenario: Scheduler shuts down cleanly
- **WHEN** the FastAPI application receives a shutdown signal
- **THEN** the scheduler shuts down without leaving orphaned threads

---

### Requirement: ser_zones database table
The system SHALL maintain a `ser_zones` table in PostgreSQL with columns: `id` (serial PK), `street_name` (text), `zone_code` (text), `zone_label` (text), `latitude` (double precision), `longitude` (double precision). A composite index on `(latitude, longitude)` SHALL exist for bounding-box queries.

#### Scenario: Table created by migration
- **WHEN** the `db-migrate` Makefile target runs
- **THEN** the `ser_zones` table and its index are created if they do not already exist

#### Scenario: Zone label derived from code
- **WHEN** a zone code is recognized (e.g., `SER-A` → `Blue`, `SER-V` → `Green`)
- **THEN** the `zone_label` column stores the human-readable label

#### Scenario: Unknown zone code stored as-is
- **WHEN** a zone code is not in the known mapping
- **THEN** `zone_label` stores the raw code value unchanged
