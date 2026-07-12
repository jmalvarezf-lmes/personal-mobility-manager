## 1. Schema

- [x] 1.1 Write Alembic migration: create `ser_zone_areas` table (`zone_number VARCHAR(10) PRIMARY KEY`, `neighbourhood TEXT NOT NULL`, `geometry_wkt TEXT NOT NULL`)
- [x] 1.2 Run migration locally against dev DB and confirm the table's schema matches design.md D4

## 2. Callejero district/barrio code parsing

- [x] 2.1 Extend callejero CSV parsing to capture `Codigo de distrito` and `Codigo de barrio` alongside the existing fields (street name, district name, zone number, coordinates)
- [x] 2.2 Unit test: a known callejero row (e.g. street "ABADA", zone "163") parses to the expected district code and barrio code alongside its existing expected fields

## 3. Barrios shapefile download and parsing

- [x] 3.1 Add a helper to download `MADRID_BARRIOS_SHP_URL` (default per proposal.md), unzip in memory, and load `BARRIOS.shp`/`.dbf` via `pyshp` — mirror the existing SER band shapefile download/parse module's structure and hostname-allowlist pattern
- [x] 3.2 Parse each barrio record's `COD_DISB` (compound district-barrio code) and `NOMBRE` (official name) fields, plus its polygon geometry
- [x] 3.3 Unit test: sample DBF/SHP fixture rows parse to the expected `COD_DISB`/`NOMBRE`/geometry values
- [x] 3.4 Unit test: hostname-allowlist rejection for a disallowed `MADRID_BARRIOS_SHP_URL` (mirroring the existing SER band shapefile fetcher's test)

## 4. Majority-vote compound code and lookup

- [x] 4.1 During the spatial join, track per-zone_number a count of matched address points per `(district_code, barrio_code)` pair
- [x] 4.2 For each zone_number, compute the majority compound code (deterministic tie-break, e.g. stable `Counter.most_common()` order) and format it as `f"{district_code}-{barrio_code}"` to match the Barrios shapefile's `COD_DISB` format
- [x] 4.3 Look up the majority compound code against the parsed Barrios records; on a match, produce a `ZoneArea` with that record's `NOMBRE` and geometry; on no match, skip that zone_number and log a warning (no fallback geometry)
- [x] 4.4 Unit test: a zone_number whose majority compound code matches a Barrios record produces a `ZoneArea` with the official name and geometry
- [x] 4.5 Unit test: a zone_number whose majority compound code does NOT match any Barrios record is absent from the result, and a warning is logged
- [x] 4.6 Unit test: two zone_numbers resolving to the same compound code produce two `ZoneArea`s with identical geometry (not deduplicated, not an error)
- [x] 4.7 Unit test: the official `NOMBRE` is used verbatim as `neighbourhood`, not any string derived from the callejero's own barrio name field (confirm no name-matching/normalization logic exists in this path at all)

## 5. Domain layer

- [x] 5.1 Confirm `SerZoneBoundaryRecord` is unchanged from `add-ser-zone-boundaries` — neighbourhood/frontier data is resolved independently via `ZoneArea`, not carried on `SerZoneBoundaryRecord` (no new field needed here, unlike the discarded Voronoi-based attempt)
- [x] 5.2 Add `ZoneArea` frozen dataclass (`zone_number`, `neighbourhood`, `geometry`) in `domain/value_objects/`
- [x] 5.3 Add `get_zone_areas() -> list[ZoneArea]` abstract method to `CityParkingDataProvider`, alongside the existing `get_records()`
- [x] 5.4 Unit tests: `ZoneArea` immutability; no `contains()` method present

## 6. Repository layer

- [x] 6.1 Add `get_zone_area(zone_number: str) -> ZoneArea | None` and `list_zone_areas() -> list[ZoneArea]` to the `SerZoneRepository` port
- [x] 6.2 Implement both methods on `PostgresSerZoneRepository`, querying `ser_zone_areas` only — never joined into `list_all()`/`find_nearest()`/`find_containing()`
- [x] 6.3 Update the ingestion insert path to write `ser_zone_areas` (one row per resolvable zone_number) within the same truncate-reload transaction as `ser_zones`/`ser_zone_streets`
- [x] 6.4 Unit tests against a test DB: `get_zone_area` returns the correct neighbourhood/geometry; returns `None` for an unknown zone_number; `list_zone_areas` returns all rows; confirms `list_all`/`find_nearest`/`find_containing` never query `ser_zone_areas`

## 7. Application layer

- [x] 7.1 Implement `MadridSerStreetsProvider.get_zone_areas()`: download/parse the Barrios shapefile, reuse the callejero join's district/barrio code data, compute majority compound codes, look up against Barrios records
- [x] 7.2 Update `IngestSerZones` to also compute and pass `ser_zone_areas` rows to the repository within the same run
- [x] 7.3 Extend the zero-records-abort guard: if `get_records()` succeeds (non-empty) but `get_zone_areas()` returns empty, abort the run before any `bulk_replace` call — same pattern as the existing `records`-empty guard
- [x] 7.4 Unit test: `records` non-empty + `zone_areas` empty raises and `repo.bulk_replace` is never called
- [x] 7.5 Unit test (resilience, learned from the discarded attempt): confirm `get_records()` and `get_zone_areas()` do not introduce any cross-call caching that could go stale across scheduled ingestion runs — per design.md D7, there should be no cache to get stale in the first place; verify each call independently re-fetches/re-parses

## 8. API layer

- [x] 8.1 Update `GET /parking/ser-zone` response schema and handler: add `neighbourhood` (via `get_zone_area`, joined at the router level same as `get_street_names`); `null` if no `ser_zone_areas` row exists
- [x] 8.2 Update `GET /parking/ser-zones` response schema and handler: add a `frontiers` array (`zone_number`, `neighbourhood`, `geometry` reprojected to WGS84 GeoJSON with the existing coordinate-precision rounding), independent of the existing `zones` array
- [x] 8.3 API tests: single-lookup endpoint includes `neighbourhood` (and gracefully returns `null` when absent); bulk endpoint's `frontiers` array has one entry per zone_number regardless of colour count; empty-DB case returns empty `frontiers` array alongside empty `zones`

## 9. Frontend map

- [x] 9.1 Update the zones API client type to include the new `frontiers` array (`zone_number`, `neighbourhood`, `geometry`)
- [x] 9.2 Render `frontiers` as a new `react-leaflet` `GeoJSON` layer with a single fixed pale grey style, added to the map BEFORE (beneath) the existing precise zone layer
- [x] 9.3 Add a tooltip to frontier polygons showing zone number and neighbourhood name
- [x] 9.4 Update Playwright e2e assertions: at least one frontier polygon element present, in addition to existing precise-zone assertions
- [x] 9.5 Manually verify in a browser: frontiers render as hatched grey shapes beneath the existing colourful precise strips, adjacent zone numbers' frontiers do not visibly overlap (or, if they share a barrio, visibly coincide, which is expected), tooltips show neighbourhood names

## 10. Cleanup and full-suite verification

- [x] 10.1 Run full backend test suite (`pytest`) and fix regressions
- [x] 10.2 Run `ruff check` / `mypy src/` and fix issues
- [x] 10.3 Run frontend `tsc`/`eslint` and fix issues
- [x] 10.4 Run a real ingestion against the live Madrid URLs (including `MADRID_BARRIOS_SHP_URL`) and confirm: ingestion completes quickly (no multi-gigabyte memory spike, no timeout — this is the property that failed with the discarded Voronoi approach), frontier polygons look like real neighbourhood boundaries, and neighbourhood names match real Madrid barrio names for a few known zones (e.g. zone 011 → "Palacio", zone 044 → "Guindalera")
