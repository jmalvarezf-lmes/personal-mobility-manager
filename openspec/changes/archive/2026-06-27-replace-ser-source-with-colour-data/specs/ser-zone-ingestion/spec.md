## MODIFIED Requirements

### Requirement: Download Madrid SER Calles CSV
The system SHALL download the Madrid SER Calles dataset (218228) from a configurable URL (`MADRID_SER_CALLES_URL` env var, default: `https://datos.madrid.es/dataset/218228-0-ser-calles/resource/218228-1-ser-calles-csv/download/218228-1-ser-calles-csv.csv`) via HTTP on each scheduled ingestion run. The response SHALL be decoded as Latin-1 (ISO-8859-1) to correctly handle accented characters.

#### Scenario: Successful download
- **WHEN** the scheduler triggers an ingestion run and the URL is reachable
- **THEN** the system downloads the CSV file content decoded as Latin-1 without writing a temp file

#### Scenario: Download failure
- **WHEN** the HTTP request returns a non-2xx status or a network error occurs
- **THEN** the system logs an error with the status code and skips the ingestion run, leaving existing data intact

#### Scenario: Configurable URL
- **WHEN** the env var `MADRID_SER_CALLES_URL` is set
- **THEN** the system uses that URL instead of the default

---

### Requirement: Parse SER spot fields from 218228 CSV
The system SHALL parse each CSV row from the 218228 SER Calles CSV (semicolon-delimited) and extract five fields: `calle` (street name), `color` (raw zone type from source), `gis_x` (UTM easting, metres), `gis_y` (UTM northing, metres), and `numero_plazas` (spot count, optional). The raw `color` value SHALL be extracted by splitting the RGB-prefixed string (e.g., `"043000255 Azul"`) on the first space and taking the remainder, yielding the plain name (e.g., `"Azul"`). That name SHALL then be validated via `MadridZoneType.from_raw()` — rows where it returns `None` SHALL be skipped. The `numero_plazas` field is optional: if it is absent, empty, or non-numeric, the system SHALL use `-1` as the spot count rather than skipping the row. Rows missing `calle`, `color`, `gis_x`, or `gis_y` SHALL be skipped.

#### Scenario: Valid row parsed
- **WHEN** a CSV row contains all fields including a numeric `numero_plazas`
- **THEN** the system produces a `ParkingSpotRecord` with street name, `zone_type` set to the `display_name` of the matched `MadridZoneType`, UTM coordinates in metres, WGS84 lat/lng, and the actual spot count

#### Scenario: Missing or non-numeric spot count uses sentinel
- **WHEN** a CSV row has an empty or non-numeric `numero_plazas` field
- **THEN** `ParkingSpotRecord.spot_count` is `-1` and the row is NOT skipped

#### Scenario: Zone type extracted from RGB-prefixed string
- **WHEN** the `color` CSV field is `"043000255 Azul"`
- **THEN** the extracted name `"Azul"` is passed to `MadridZoneType.from_raw()` and `ParkingSpotRecord.zone_type` is `"Azul"`

#### Scenario: Multi-word zone type extracted correctly
- **WHEN** the `color` CSV field is `"081209246 Alta Rotación"`
- **THEN** the extracted name `"Alta Rotación"` is passed to `MadridZoneType.from_raw()` and `ParkingSpotRecord.zone_type` is `"Alta Rotación"`

#### Scenario: Unrecognised zone type skips the row
- **WHEN** a CSV row has a zone type string not recognised by `MadridZoneType.from_raw()`
- **THEN** the system skips that row, logs a warning with the unrecognised value, and increments the skipped-row counter

#### Scenario: Row with missing required field skipped
- **WHEN** a CSV row has an empty `calle`, `color`, `gis_x`, or `gis_y` field
- **THEN** the system skips that row and increments the skipped-row counter

---

### Requirement: Use UTM coordinates directly without centimetre conversion
The system SHALL use `gis_x` and `gis_y` from the 218228 CSV directly as EPSG:25830 easting and northing in metres. No division by 100 SHALL be applied. Both values SHALL be stored as-is and also reprojected to WGS84 (EPSG:4326) for bounding-box indexing.

#### Scenario: Coordinates used without conversion
- **WHEN** a row has `gis_x = 438727.67` and `gis_y = 4473037.77`
- **THEN** `utm_x = 438727.67` and `utm_y = 4473037.77` (no division applied)

#### Scenario: Valid UTM coordinates reprojected
- **WHEN** a row contains valid UTM X/Y values in EPSG:25830 (metres)
- **THEN** the system produces a WGS84 lat/lng pair within the bounding box of the Community of Madrid (lat 39.8–41.2, lng -4.6–-2.9)

#### Scenario: Invalid coordinate values skipped
- **WHEN** a row contains non-numeric coordinate values
- **THEN** the system skips that row with a warning log

---

### Requirement: Upsert SER zone data into PostgreSQL
The system SHALL store parsed records in the `ser_zones` PostgreSQL table using a truncate-and-reload strategy within a single transaction. The stored fields SHALL include `street_name`, `zone_type`, `spot_count`, `latitude`, `longitude`, `utm_x`, `utm_y`.

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

### Requirement: Scheduled periodic ingestion via provider interface
The system SHALL run ingestion automatically on a configurable interval (default: every 24 hours) for each registered `CityParkingDataProvider`. The scheduler SHALL call `provider.get_records()` and delegate to the `IngestCityParkingData` use case. The scheduler SHALL NOT contain city-specific logic.

#### Scenario: Scheduler starts on app boot
- **WHEN** the FastAPI application starts
- **THEN** the APScheduler `BackgroundScheduler` starts and schedules one ingestion job per registered provider

#### Scenario: Provider failure does not stop other providers
- **WHEN** one city provider raises an exception during `get_records()`
- **THEN** the scheduler logs the failure and continues scheduling/running the other providers

## REMOVED Requirements

### Requirement: Download Madrid callejero CSV
**Reason**: Replaced by the 218228 SER Calles dataset which is the authoritative source and includes colour information absent from the callejero.
**Migration**: Set `MADRID_SER_CALLES_URL` env var; remove `MADRID_CALLEJERO_URL` from environment config.

---

### Requirement: Parse SER zone fields from CSV (callejero columns)
**Reason**: The 218228 CSV has different columns (`calle`, `color` raw field → `zone_type` domain field, `gis_x`, `gis_y`, `numero_plazas`) replacing the callejero columns (`Nombre de la vía`, `Zona Servicio Estacionamiento Regulado`, centimetre coordinate columns).
**Migration**: No migration needed; the `MadridSerCallesProvider` replaces `CallejeroCsvParser` entirely.

---

### Requirement: Convert centimetre coordinates to UTM metres and reproject to WGS84
**Reason**: The 218228 CSV ships coordinates already in UTM metres; no ÷100 conversion is needed.
**Migration**: No action; the new parser reads metre values directly.

---

### Requirement: Zone code "000" row filtering
**Reason**: The 218228 CSV contains only SER zone rows by definition; there is no non-zone sentinel value to filter.
**Migration**: No action; filtering logic removed from the parser.
