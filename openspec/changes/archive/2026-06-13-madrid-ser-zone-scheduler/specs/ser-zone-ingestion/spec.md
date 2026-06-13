## ADDED Requirements

### Requirement: Download Madrid callejero CSV
The system SHALL download the Madrid callejero dataset from a configurable URL (`MADRID_CALLEJERO_URL` env var) via HTTP on each scheduled ingestion run. The response SHALL be decoded as Latin-1 (ISO-8859-1) to correctly handle accented characters in column headers.

#### Scenario: Successful download
- **WHEN** the scheduler triggers an ingestion run and the URL is reachable
- **THEN** the system downloads the CSV file content decoded as Latin-1 without writing a temp file

#### Scenario: Download failure
- **WHEN** the HTTP request returns a non-2xx status or a network error occurs
- **THEN** the system logs an error with the status code and skips the ingestion run, leaving existing data intact

#### Scenario: Configurable URL
- **WHEN** the env var `MADRID_CALLEJERO_URL` is set
- **THEN** the system uses that URL instead of the default

---

### Requirement: Parse SER zone fields from CSV
The system SHALL parse each CSV row from `200075-1-callejero-csv.csv` (semicolon-delimited, all fields quoted) and extract four fields using accent-insensitive header matching: `Nombre de la vía` (street name), `Zona Servicio Estacionamiento Regulado` (zone code), `Coordenada X (Guia Urbana) cm` (UTM easting, centimetres), and `Coordenada Y (Guia Urbana) cm` (UTM northing, centimetres). Rows missing any of these four fields SHALL be skipped.

#### Scenario: Valid row parsed
- **WHEN** a CSV row contains all four required fields with valid values
- **THEN** the system produces a `SerZoneRecord` with street name, zone code, UTM coordinates in metres (cm / 100), and WGS84 lat/lng

#### Scenario: Zone code "000" skipped
- **WHEN** a CSV row has zone code `"000"` (no SER zone assigned to that address)
- **THEN** the system skips that row and increments a skipped-row counter

#### Scenario: Row with empty or missing zone field skipped
- **WHEN** a CSV row has an empty SER zone code field
- **THEN** the system skips that row and increments a skipped-row counter

#### Scenario: Column detection is accent-insensitive
- **WHEN** the CSV column header `Nombre de la vía` is decoded with or without the accent on `í`
- **THEN** the system still resolves the street column correctly (NFKD normalisation strips accents before matching)

---

### Requirement: Convert centimetre coordinates to UTM metres and reproject to WGS84
The system SHALL divide raw centimetre coordinate values by 100 to obtain EPSG:25830 easting/northing in metres, then reproject to WGS84 (EPSG:4326). Both the UTM metre values and the WGS84 lat/lng SHALL be stored.

#### Scenario: Centimetre values converted to metres
- **WHEN** a row contains `"0044059400"` in the X column
- **THEN** `utm_x = 440594.0` metres (÷ 100)

#### Scenario: Valid UTM coordinates reprojected
- **WHEN** a row contains valid UTM X/Y values in EPSG:25830 (metres)
- **THEN** the system produces a WGS84 lat/lng pair within the bounding box of the Community of Madrid (lat 39.8–41.2, lng -4.6–-2.9)

#### Scenario: Invalid coordinate values skipped
- **WHEN** a row contains non-numeric coordinate values
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
The system SHALL maintain a `ser_zones` table in PostgreSQL with columns: `id` (serial PK), `street_name` (text), `zone_code` (text), `zone_label` (text), `latitude` (double precision), `longitude` (double precision), `utm_x` (double precision), `utm_y` (double precision). A composite index on `(latitude, longitude)` SHALL exist for bounding-box queries. `utm_x` and `utm_y` store EPSG:25830 easting/northing in metres and are used for Euclidean distance calculation.

#### Scenario: Table created by migration
- **WHEN** the `db-migrate` Makefile target runs
- **THEN** the `ser_zones` table and its index are created if they do not already exist

#### Scenario: Zone code used as label
- **WHEN** a zone code is parsed from the CSV (e.g., `"011"`, `"042"`, `"163"`)
- **THEN** `zone_label` stores the raw zone code unchanged (numeric SER codes have no standard colour mapping)

#### Scenario: utm_x and utm_y stored alongside WGS84
- **WHEN** a record is inserted
- **THEN** both the WGS84 lat/lng (for bounding-box SQL index) and the UTM metre coordinates (for Euclidean distance ranking) are persisted
