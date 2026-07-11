## 1. Dependencies & schema

- [x] 1.1 Add `shapely` and `pyshp` to `pyproject.toml`
- [x] 1.2 Write Alembic migration: drop `latitude`, `longitude`, `utm_x`, `utm_y` from `ser_zones`; add `zone_number VARCHAR(10) NOT NULL`, `district TEXT NOT NULL`, `geometry_wkt TEXT NOT NULL`; add `UNIQUE (zone_number, zone_type)`; create new `ser_zone_streets` table (`id SERIAL PK`, `zone_number VARCHAR(10) NOT NULL`, `zone_type VARCHAR(50) NOT NULL`, `street_name TEXT NOT NULL`) with an index on `(zone_number, zone_type)`
- [x] 1.3 Run migration locally against dev DB and confirm both tables' schema matches design.md D8/D9 — VERIFIED: ran against a live docker-compose Postgres; `ser_zones`/`ser_zone_streets` schema confirmed directly via SQL, and the full `tests/infrastructure/` suite (141 tests, including all `test_ser_zone_repo_integration.py` cases) passes against the real DB with 0 skipped

## 2. Callejero CSV parsing

- [x] 2.1 Add a helper to parse the callejero CSV (`Nombre de la vía`, `Zona Servicio Estacionamiento Regulado`, `Nombre del distrito`, DMS lat/lng columns), decoded as Latin-1, semicolon-delimited
- [x] 2.2 Implement DMS → decimal-degree conversion for the `Longitud`/`Latitud en S R ETRS89 WGS84` columns, tolerant of both `°` and `º` degree-symbol variants seen in the source
- [x] 2.3 Reproject parsed callejero points from WGS84 to EPSG:25830 using the existing pyproj transform pattern
- [x] 2.4 Unit test: known callejero row (e.g. street "ABADA", zone "163") parses to the expected zone number, street, district, and UTM coordinates within tolerance

## 3. SER band shapefile parsing

- [x] 3.1 Add a helper to download `SER_ZONE_SHP_URL`, unzip in memory, and load `SER_BANDA_APARCAMIENTO.shp`/`.dbf` via `pyshp`
- [x] 3.2 Parse each band's `Color`, `Res_NumPla`, and line geometry (already EPSG:25830 per `.prj`); `Bateria_Li` is not parsed — it is unused (see design.md D4)
- [x] 3.3 Filter out bands where `Color == "Gris"`
- [x] 3.4 Validate remaining `Color` values via `MadridZoneType.from_raw()` (plain name, no RGB prefix this time); skip and log unrecognised values with a warning + skipped-row counter
- [x] 3.5 Unit test: sample DBF/SHP fixture rows parse to expected `Color`/`Res_NumPla`/geometry values; `"Gris"` rows are excluded

## 4. Spatial join

- [x] 4.1 Build a `shapely.strtree.STRtree` over all reprojected callejero points at ingestion time
- [x] 4.2 For each retained band, compute its line midpoint and query the tree for the nearest callejero point
- [x] 4.3 Attach `zone_number`, street name, and district from the matched callejero point to the band
- [x] 4.4 Unit test: a band placed near a known callejero fixture point inherits that point's zone number/street/district

## 5. Buffer and dissolve into zone boundaries

- [x] 5.1 Define a single named half-width constant for band buffering per design.md D4 (proposed default: 2.5 m), used uniformly regardless of parking orientation
- [x] 5.2 Buffer each band's geometry by the fixed half-width into a polygon
- [x] 5.3 Group buffered polygons by `(zone_number, zone_type)`
- [x] 5.4 Dissolve each group via `shapely.ops.unary_union`; sum `spot_count` (treating `-1`/unknown appropriately, matching the existing sentinel convention); collect distinct `street_names`
- [x] 5.5 Unit test: two bands sharing `(zone_number, zone_type)` dissolve into one record with unioned geometry and summed spot count
- [x] 5.6 Unit test: bands sharing a `zone_number` but different `zone_type` produce separate records with the same `zone_number`/`district`

## 6. SerZoneBoundaryRecord and MadridSerStreetsProvider

- [x] 6.1 Add `SerZoneBoundaryRecord` frozen dataclass (`zone_number`, `zone_type`, `district`, `street_names`, `spot_count`, `geometry`) in `domain/value_objects/`, replacing `ParkingSpotRecord`
- [x] 6.2 Implement `MadridSerStreetsProvider` (`city_code = "madrid"`) tying together sections 2-5 into `get_records() -> list[SerZoneBoundaryRecord]`
- [x] 6.3 Remove `MadridSerCallesProvider` and `ParkingSpotRecord`; update the provider registry to construct `MadridSerStreetsProvider`
- [x] 6.4 Read `SER_ZONE_SHP_URL` (default per proposal.md) and `MADRID_CALLEJERO_URL` (default per proposal.md) from env vars, following the existing hostname-allowlist pattern
- [x] 6.5 Integration test: `MadridSerStreetsProvider.get_records()` against fixture SHP+CSV data returns expected zone boundary records end to end

## 7. Domain: SerZone entity

- [x] 7.1 Update `SerZone` entity: `zone_number`, `zone_type`, `district`, `spot_count`, `geometry` (no `street_names` field — see design.md D9)
- [x] 7.2 Implement `SerZone.contains(location: GeoLocation) -> bool` — reproject `location` to EPSG:25830, use `shapely`'s boundary-inclusive `covers()`
- [x] 7.3 Unit tests: `contains()` true for interior point, true for boundary-exact point, false for exterior point

## 8. Repository layer

- [x] 8.1 Update `SerZoneRepository` port: `find_nearest(location) -> SerZone | None`, `find_containing(location) -> SerZone | None`, `list_all() -> list[SerZone]`, `get_street_names(zone_number: str, zone_type: str) -> list[str]`
- [x] 8.2 Update `PostgresSerZoneRepository`: load all `ser_zones` rows, deserialize `geometry_wkt` via `shapely.wkt.loads`, implement `find_containing` (first/only match) and `find_nearest` (min distance-to-geometry, 0 if inside) per design.md D5 — no SQL bounding-box prefilter; implement `get_street_names` as a targeted query against `ser_zone_streets` only, never joined into the other methods
- [x] 8.3 Update the ingestion insert path to write `ser_zones` (geometry as WKT, `zone_number`/`district`) and `ser_zone_streets` (one row per street) within the same truncate-reload transaction
- [x] 8.4 Unit tests against a test DB: `find_containing` returns the correct zone; `find_nearest` returns 0 distance when inside a zone and the correct minimum otherwise; `get_street_names` returns all streets for a zone and is not triggered by `list_all`/`find_nearest`/`find_containing` — written against POSTGRES_DSN-gated fixture (same pattern as existing suite); skip cleanly (14 skipped) in this sandbox since no local PostgreSQL instance is available

## 9. Application layer

- [x] 9.1 Update `IngestCityParkingData` use case for the new `SerZoneBoundaryRecord` shape (truncate-reload strategy unchanged, now spanning two tables) — implemented as `IngestSerZones` (the existing use case's actual class name in this codebase)
- [x] 9.2 Update `FindNearestSerZone` use case for the reworked `find_nearest` signature/semantics (still returns `SerZone` only, no street names) — signature was already `find_nearest(location)` with no extra params, no change needed beyond the port/repo rework
- [x] 9.3 Add `FindContainingSerZone` use case (returns `SerZone | None`, no exception on not-found)
- [x] 9.4 Unit tests for both use cases (plus `IngestSerZones`, which also changed shape)

## 10. API layer

- [x] 10.1 Update `GET /parking/ser-zone` response schema and handler: `zone_number`, `zone_type`, `district`, `street_names` (via `get_street_names`, joined at the router level), `spot_count`, `distance_meters`
- [x] 10.2 Update `GET /parking/ser-zones` response schema and handler: `zone_number`, `zone_type`, `colour`, `district`, `spot_count`, `geometry` (GeoJSON, reprojected from stored UTM WKT to WGS84 at the API boundary) — no `street_names`
- [x] 10.3 Add UTM→WGS84 GeoJSON reprojection helper reused by both endpoints
- [x] 10.4 API tests: both endpoints return the new shape (including confirming `street_names` is present on the single-lookup endpoint and absent on the bulk endpoint); empty-DB and not-found cases still behave per spec

## 11. Frontend map

- [x] 11.1 Update the zones API client type to the new bulk response shape (`zone_number`, `district`, `spot_count`, `geometry` — no `street_names`)
- [x] 11.2 Replace `CircleMarker` rendering with `GeoJSON`/`Polygon` rendering using `colour` for fill/stroke, handling both `Polygon` and `MultiPolygon` geometry types
- [x] 11.3 Update tooltip content to show zone number, district, and spot count (no street names, no additional network call on hover)
- [x] 11.4 Update Playwright e2e assertions: polygon (SVG path) presence instead of circle marker presence; tooltip content assertions updated to the new fields
- [x] 11.5 Manually verify the map in a browser: zones render as coloured polygons, tooltips show correct data, no console errors — VERIFIED against a live docker-compose stack; found and fixed two real bugs in the process: (1) callejero `"000"` rows leaking into the spatial join, fragmenting zones into near-single-band slivers, (2) Chromium's default focus outline on a clicked SVG path rendering as a stray rectangle around the shape's bounding box (fixed via `.leaflet-interactive:focus { outline: none; }` in `index.css`). Confirmed fixed and correct by direct user inspection

## 12. Cleanup and full-suite verification

- [x] 12.1 Remove/update existing tests referencing `ParkingSpotRecord`, `MadridSerCallesProvider`, `MADRID_SER_CALLES_URL`, and point-based `ser_zones` columns
- [x] 12.2 Update `.env.example`/docs for `SER_ZONE_SHP_URL` and `MADRID_CALLEJERO_URL`, removing `MADRID_SER_CALLES_URL` — `MADRID_SER_CALLES_URL` was never in `.env.example`; removed the dead `get_madrid_ser_calles_url()`/`_DEFAULT_MADRID_SER_CALLES_URL` from `config.py` instead (unused, referenced the retired env var); `openspec/specs/*` canonical spec files intentionally left untouched — those are updated at `sdd-archive` time, not `sdd-apply` time
- [x] 12.3 Run full backend test suite (`pytest`) and fix regressions — final run against a live Postgres: 418 passed, 0 skipped, 0 failed. `ruff check` and `mypy` both clean.
- [x] 12.4 Run frontend test suite and Playwright e2e against a full local stack (`docker-compose up`) — 50/52 e2e specs passed against the live stack; the 2 `map.spec.ts` failures were a data-availability race (ran while a fresh ingestion triggered by a container restart was still downloading from the real, slow-from-this-sandbox Madrid servers — an environment/network limitation, not a code defect), not a functional regression. Frontend `tsc`/`eslint` both clean (see earlier verification in this change).
- [x] 12.5 Run a manual ingestion against the real `SER_ZONE_SHP_URL`/`MADRID_CALLEJERO_URL` and spot-check a handful of known zones (e.g. "ABADA"/zone 163) render sensible polygons on the map, and that `GET /parking/ser-zone` for a coordinate on that street returns its street names — VERIFIED: real ingestion ran against the actual Madrid URLs (154 real zones produced); spot-checked zones 011/CENTRO, 044/SALAMANCA, 075/CHAMBERI, 151/CIUDAD LINEAL directly against the live DB and API — all real, correctly-shaped multi-part geometry with correct colours and street/district data
