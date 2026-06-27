## Why

The current implementation uses the Madrid Callejero address registry (200075) as a proxy for SER zone data — it provides numeric zone codes but no colour information. SER parking fees are colour-dependent (Verde cheapest → Azul → Naranja/Rojo → Alta Rotación most expensive), making colour the essential field for any pricing or user-facing feature. The 218228 SER Calles dataset is the authoritative source: it maps each parking spot to its colour, spot count, parking orientation, and UTM coordinates already in metres, eliminating two transformation steps that exist only because the wrong source was used.

## What Changes

- **Replace** the Madrid Callejero CSV source (200075) with the SER Calles CSV (218228) as the sole Madrid SER data source
- **Add `zone_type` field** to the `SerZone` entity — a `ZoneType` instance produced by each city's own implementation of a domain abstract class (e.g., `MadridZoneType.Azul`); the city-specific subclass defines both how to parse from raw source data and the `display_name` stored in the DB and returned in the API
- **Add `spot_count` field** (number of parking spots at the address) to `SerZone` and the API response; the field is optional — when `numero_plazas` is absent or unparseable in the source the system stores `-1` to signal unknown rather than defaulting to zero
- **Remove ÷100 coordinate conversion** — the new file ships coordinates already in UTM metres (EPSG:25830), no centimetre division needed
- **Remove `"000"` zone filtering** — all rows in the new file are SER zones by definition; no non-zone rows exist
- **Rename env var** `MADRID_CALLEJERO_URL` → `MADRID_SER_CALLES_URL`; the dataset URL is always read from this env var (with a sensible default) so the URL can be updated without a code change if Madrid republishes the dataset
- **Introduce `CityParkingDataProvider` port** in the domain layer — an abstract interface that decouples ingestion from any specific city or file format, enabling future cities to plug in without touching the use case or scheduler
- **Implement `MadridSerCallesProvider`** as the first concrete provider, replacing `CallejeroCsvParser`
- **Alembic migration** to add `zone_type` (VARCHAR, not-null) and `spot_count` (INTEGER, not-null) columns and drop the now-redundant `zone_label` column
- Update API response to surface `zone_type` and `spot_count`

## Capabilities

### New Capabilities

- `city-parking-data-provider`: Abstract port + registry for city parking data ingestion. Defines the contract any city-specific provider must satisfy, including a `ZoneType` abstract class each city implements to enumerate and validate its parking zone classifications.

### Modified Capabilities

- `ser-zone-ingestion`: New CSV source (218228), new fields (zone_type, spot_count), new parsing logic (no ÷100, no zone-code filtering, zone type parsed via `MadridZoneType.from_raw()`), new env var, and the ingestion use case now accepts a `CityParkingDataProvider` rather than calling Madrid-specific code directly.
- `ser-zone-query`: REST response gains `zone_type` and `spot_count` fields; `zone_label` is removed since `zone_type` replaces it as the human-readable zone classification.

## Impact

- **Domain**: `SerZone` entity (add `zone_type`, `spot_count`; remove `zone_label`), new `CityParkingDataProvider` port, new `ZoneType` abstract class, new `ParkingSpotRecord` value object
- **Infrastructure**: `MadridSerCallesProvider` (new, replaces `CallejeroCsvParser`), `ser_zones` ORM table (add columns), `SerZonePostgresRepository` (store/retrieve new fields)
- **Application**: `IngestSerZones` use case accepts provider via constructor injection
- **Presentation**: `/parking/ser-zone` response schema updated
- **Config**: `MADRID_CALLEJERO_URL` env var renamed to `MADRID_SER_CALLES_URL`; URL always resolved from env var
- **DB**: Alembic migration required (additive + column drop — truncate-reload ingestion means no data migration needed)
- **Tests**: Unit tests for new parser, integration tests for updated repo and API response
