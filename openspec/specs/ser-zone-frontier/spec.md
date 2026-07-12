## Purpose

Resolves a legible, presentation-only "frontier" boundary and neighbourhood name for each SER zone_number, sourced from Madrid's official Barrios administrative shapefile via an exact compound-code lookup (not synthesized geometry). This capability owns the `ser_zone_areas` table, the Barrios shapefile download/parse, and the majority-vote compound-code resolution that maps each zone_number to its official barrio. Frontier data is strictly presentation-only and never affects containment/ticket-liability logic (`SerZone.contains()`).

## Requirements

### Requirement: ser_zone_areas database table
The system SHALL maintain a `ser_zone_areas` table in PostgreSQL with columns: `zone_number` (varchar(10), primary key), `neighbourhood` (text, not-null), `geometry_wkt` (text, not-null, WKT in EPSG:25830). This table is keyed by `zone_number` alone — both the frontier geometry and the neighbourhood name are zone_number-scoped concepts, independent of `zone_type`.

#### Scenario: Table created by migration
- **WHEN** the `db-migrate` Makefile target runs
- **THEN** the `ser_zone_areas` table is created if it does not already exist

#### Scenario: One row per zone_number regardless of colour count
- **WHEN** a zone_number has three `ser_zones` rows (one per colour: Azul, Verde, Alta Rotación)
- **THEN** `ser_zone_areas` still has exactly one row for that zone_number

### Requirement: Download and parse the Madrid Barrios administrative boundary shapefile
The system SHALL download the Madrid Barrios shapefile (`MADRID_BARRIOS_SHP_URL` env var, default `https://geoportal.madrid.es/fsdescargas/IDEAM_WBGEOPORTAL/LIMITES_ADMINISTRATIVOS/Barrios/Barrios.zip`) as a zip archive and extract its `.shp`/`.dbf` components in memory, on each scheduled ingestion run. Each parsed record SHALL expose its `COD_DISB` field (a compound district-barrio code, e.g. `"1-1"`), its `NOMBRE` field (the official barrio name), and its polygon geometry (already EPSG:25830 per its `.prj`).

#### Scenario: Successful download and parse
- **WHEN** the scheduler triggers an ingestion run and the URL is reachable
- **THEN** the system downloads and parses all barrio records, without writing to a permanent temp file

#### Scenario: Download failure aborts the run
- **WHEN** the HTTP request returns a non-2xx status or a network error occurs
- **THEN** the system logs an error and skips the ingestion run, leaving existing data intact (same failure-handling contract as the other two Madrid sources)

#### Scenario: Configurable URL
- **WHEN** the `MADRID_BARRIOS_SHP_URL` env var is set
- **THEN** the system uses that URL instead of the default

### Requirement: Frontier resolved via compound-code lookup against official barrio boundaries
For each `zone_number`, the system SHALL determine its majority `(district_code, barrio_code)` pair — from the callejero CSV's `Codigo de distrito`/`Codigo de barrio` columns, matched to that zone_number's bands via the same spatial join used for street/district resolution, weighted by matched-address-point count — format it as `f"{district_code}-{barrio_code}"`, and look up that compound key directly against the Barrios shapefile's `COD_DISB` field. On a match, the zone_number's frontier geometry SHALL be that barrio's polygon, and its neighbourhood name SHALL be that barrio's official `NOMBRE` field (not any string derived from the callejero's own free-text barrio name). This frontier geometry SHALL NOT be used by `SerZone.contains()` or any containment/ticket-liability logic — it is presentation-only.

#### Scenario: Compound code resolves to the correct official barrio
- **WHEN** a zone_number's majority compound code is `"1-1"`
- **THEN** its frontier geometry is the Barrios record with `COD_DISB == "1-1"`'s polygon, and its neighbourhood is that record's `NOMBRE` (e.g. `"Palacio"`)

#### Scenario: Zone number cannot be used as a shortcut into the barrio dataset
- **WHEN** resolving a zone_number's frontier
- **THEN** the system SHALL NOT use the raw SER `zone_number` value itself as a lookup key against the Barrios shapefile — only the compound `(district_code, barrio_code)` code derived from the callejero join is used, since SER zone numbers and barrio codes are independent numbering schemes that only coincidentally overlap for some values

#### Scenario: Official name overrides callejero spelling
- **WHEN** the callejero's free-text barrio name for a zone_number's majority barrio differs in spelling/accents/articles from the Barrios shapefile's official `NOMBRE` (e.g. callejero says "EL PILAR", official record says "Pilar")
- **THEN** the returned `neighbourhood` is the official `NOMBRE` ("Pilar"), not the callejero's spelling

#### Scenario: Unresolvable zone_number is skipped, not given a fallback shape
- **WHEN** a zone_number's majority compound code does not match any Barrios record
- **THEN** that zone_number is skipped entirely (absent from `ser_zone_areas`), a warning is logged, and no synthesized or approximated geometry is produced in its place

#### Scenario: Multiple zone numbers sharing a barrio share identical frontier geometry
- **WHEN** two different zone_numbers both resolve to the same compound code
- **THEN** both zone_numbers' `ser_zone_areas` rows contain the same frontier geometry and neighbourhood name — this is expected, not an error
