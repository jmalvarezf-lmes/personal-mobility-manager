### Requirement: Download SER zone boundary shapefile and callejero CSV
The system SHALL download the Madrid SER band shapefile (`SER_ZONE_SHP_URL` env var, default `https://geoportal.madrid.es/fsdescargas/IDEAM_WBGEOPORTAL/MOVILIDAD/ZONA_SER/SHP_ZIP.zip`) as a zip archive and extract `SER_BANDA_APARCAMIENTO.shp`/`.dbf`/`.prj`/`.shx` in memory, and SHALL download the callejero CSV (`MADRID_CALLEJERO_URL` env var, default `https://datos.madrid.es/dataset/200075-0-callejero/resource/200075-1-callejero-csv/download/200075-1-callejero-csv.csv`) decoded as Latin-1, on each scheduled ingestion run.

#### Scenario: Successful download of both sources
- **WHEN** the scheduler triggers an ingestion run and both URLs are reachable
- **THEN** the system downloads and extracts the shapefile components and downloads the callejero CSV content, without writing either to a permanent temp file

#### Scenario: Download failure on either source aborts the run
- **WHEN** either HTTP request returns a non-2xx status or a network error occurs
- **THEN** the system logs an error identifying which source failed and skips the ingestion run, leaving existing data intact

#### Scenario: Configurable URLs
- **WHEN** `SER_ZONE_SHP_URL` or `MADRID_CALLEJERO_URL` env vars are set
- **THEN** the system uses those URLs instead of the defaults

---

### Requirement: Parse and join SER zone boundary sources
The system SHALL parse each shapefile band record (`Color`, `Res_NumPla`, and line geometry), discard bands where `Color` is `"Gris"`, and parse each callejero row's `Zona Servicio Estacionamiento Regulado` (zone number), `Nombre de la vía` (street name), `Nombre del distrito` (district), `Codigo de distrito` (district code), `Codigo de barrio` (barrio code), and WGS84 DMS coordinates. Callejero rows where `Zona Servicio Estacionamiento Regulado == "000"` (Madrid's code meaning the address is not part of any SER zone) SHALL be excluded from the callejero points used to build the spatial join index — they are not valid join targets. The system SHALL reproject the remaining callejero coordinates to EPSG:25830 and spatially join each band to its nearest (SER-zoned) callejero point to assign `zone_number`, street name, district, district code, and barrio code.

#### Scenario: Band matched to nearest address point
- **WHEN** a retained band's midpoint is queried against the callejero spatial index
- **THEN** the band inherits the `zone_number`, street name, district, district code, and barrio code of the nearest SER-zoned callejero address point

#### Scenario: Non-SER-zoned callejero rows are excluded from the join index
- **WHEN** a callejero row has `Zona Servicio Estacionamiento Regulado == "000"`
- **THEN** that row is not added to the spatial join index, even though it has valid street/coordinate data, so no band can be joined to it

#### Scenario: Unrecognised zone type skips the band
- **WHEN** a band's `Color` field (after the `Gris` filter) does not match any `MadridZoneType` member
- **THEN** the system skips that band, logs a warning with the unrecognised value, and increments the skipped-row counter

### Requirement: Buffer and dissolve bands into zone boundary polygons
The system SHALL buffer each retained band's line geometry into a polygon using a single fixed half-width constant (parking orientation is not used to vary the width — a zone-containment check does not need per-bay geometric precision), then group buffered polygons by `(zone_number, zone_type)` and dissolve each group into a single polygon or multi-polygon geometry, summing `spot_count` and collecting all distinct street names per group. The dissolved geometry SHALL be simplified (tolerance 0.5 metres, topology-preserving) before being stored, to keep coordinate counts and payload sizes practical for the map to render.

#### Scenario: Bands dissolve into one zone geometry
- **WHEN** all bands sharing a `(zone_number, zone_type)` pair are dissolved
- **THEN** the resulting `SerZoneBoundaryRecord.geometry` covers the union of their buffered areas, and `spot_count` is their sum

#### Scenario: Dissolved geometry is simplified before storage
- **WHEN** a zone's dissolved geometry has a large coordinate count (e.g. from many unioned band parts)
- **THEN** the stored `SerZoneBoundaryRecord.geometry` is simplified at a 0.5 metre tolerance, preserving overall shape and topology while substantially reducing coordinate count

#### Scenario: Physically discontinuous zone produces a multi-part geometry
- **WHEN** a zone's dissolved bands are not all spatially contiguous
- **THEN** the resulting geometry is a valid multi-polygon, not an error

#### Scenario: Buffer width is uniform across all bands
- **WHEN** any two retained bands with different (or unknown) parking orientation are buffered
- **THEN** both use the same fixed half-width constant

---

### Requirement: Upsert SER zone data into PostgreSQL
The system SHALL store parsed zone boundary records in PostgreSQL using a truncate-and-reload strategy within a single transaction, across three tables: `ser_zones` (fields `zone_number`, `zone_type`, `district`, `spot_count`, `geometry_wkt`), `ser_zone_streets` (one row per `(zone_number, zone_type, street_name)` triple), and `ser_zone_areas` (one row per resolvable `zone_number`, holding its Barrios-shapefile-derived frontier geometry and neighbourhood name — see the `ser-zone-frontier` capability).

#### Scenario: Successful ingestion run
- **WHEN** parsing and joining completes with at least one valid zone boundary record
- **THEN** the system truncates `ser_zones`, `ser_zone_streets`, and `ser_zone_areas`, and bulk-inserts all valid records into all three tables in a single transaction, then commits

#### Scenario: Partial failure rolls back
- **WHEN** an error occurs during bulk insert into any of the three tables
- **THEN** the transaction is rolled back and the previous data in all three tables remains unchanged

#### Scenario: Ingestion run logs summary
- **WHEN** an ingestion run completes (success or failure)
- **THEN** the system logs: total bands downloaded, bands parsed, bands skipped, zone boundary records inserted, and elapsed time

#### Scenario: Zero parsed records aborts the run
- **WHEN** parsing and joining completes with zero valid zone boundary records (not a download/HTTP failure, but a successful fetch that yields no usable data)
- **THEN** the system aborts the run without truncating or modifying `ser_zones`/`ser_zone_streets`/`ser_zone_areas`, logs an error, and the failure propagates the same way a download failure would

#### Scenario: Zero resolved zone areas while records is non-empty also aborts the run
- **WHEN** `get_records()` returns a non-empty list but `get_zone_areas()` returns an empty list (e.g. the Barrios shapefile fetch degraded to zero usable records)
- **THEN** the system aborts the run without truncating or modifying any of the three tables, logs an error, and does not silently leave `ser_zone_areas` empty while `ser_zones`/`ser_zone_streets` update

---

### Requirement: Scheduled periodic ingestion via provider interface
The system SHALL run ingestion automatically on a configurable interval (default: every 24 hours) for each registered `CityParkingDataProvider`. The scheduler SHALL call `provider.get_records()` and delegate to the `IngestCityParkingData` use case. The scheduler SHALL NOT contain city-specific logic.

#### Scenario: Scheduler starts on app boot
- **WHEN** the FastAPI application starts
- **THEN** the APScheduler `BackgroundScheduler` starts and schedules one ingestion job per registered provider

#### Scenario: Provider failure does not stop other providers
- **WHEN** one city provider raises an exception during `get_records()`
- **THEN** the scheduler logs the failure and continues scheduling/running the other providers

#### Scenario: Configurable interval
- **WHEN** the env var `INGESTION_INTERVAL_HOURS` is set to a positive integer
- **THEN** the scheduler uses that interval instead of the 24-hour default

#### Scenario: Scheduler shuts down cleanly
- **WHEN** the FastAPI application receives a shutdown signal
- **THEN** the scheduler shuts down without leaving orphaned threads

---

### Requirement: ser_zones database table
The system SHALL maintain a `ser_zones` table in PostgreSQL with columns: `id` (serial PK), `zone_number` (varchar(10), not-null), `zone_type` (varchar(50), not-null), `district` (text, not-null), `spot_count` (integer, not-null, default -1), `geometry_wkt` (text, not-null, WKT in EPSG:25830). A `UNIQUE (zone_number, zone_type)` constraint SHALL exist. `spot_count = -1` is the sentinel for unknown spot count. Street names are NOT stored on this table — see the `ser_zone_streets` requirement below.

#### Scenario: Table created by migration
- **WHEN** the `db-migrate` Makefile target runs
- **THEN** the `ser_zones` table and its unique constraint are created if they do not already exist

#### Scenario: Geometry stored in UTM metres
- **WHEN** a zone boundary record is inserted
- **THEN** `geometry_wkt` contains a valid WKT `POLYGON` or `MULTIPOLYGON` in EPSG:25830 coordinates

#### Scenario: Duplicate zone_number and zone_type rejected
- **WHEN** an insert would create a second row with the same `(zone_number, zone_type)` pair within one ingestion transaction
- **THEN** the unique constraint prevents it (the ingestion pipeline dissolves bands before insert, so this should not occur in practice)

### Requirement: ser_zone_streets database table
The system SHALL maintain a `ser_zone_streets` table in PostgreSQL with columns: `id` (serial PK), `zone_number` (varchar(10), not-null), `zone_type` (varchar(50), not-null), `street_name` (text, not-null), with an index on `(zone_number, zone_type)`. Each row associates one street name with one zone; a zone spanning multiple streets has multiple rows.

#### Scenario: Table created by migration
- **WHEN** the `db-migrate` Makefile target runs
- **THEN** the `ser_zone_streets` table and its index are created if they do not already exist

#### Scenario: Zone with multiple streets has multiple rows
- **WHEN** a `SerZoneBoundaryRecord` with three distinct `street_names` is inserted
- **THEN** three rows are inserted into `ser_zone_streets`, all sharing that record's `zone_number` and `zone_type`
