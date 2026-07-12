## MODIFIED Requirements

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
