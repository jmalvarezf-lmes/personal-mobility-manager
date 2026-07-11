## Context

`ser_zones` today holds one row per parking spot/street segment, sourced from the Madrid 218228 "SER Calles" CSV — a single lat/lng point per row, no boundary. `SerZoneRepository.find_nearest()` answers "what's the closest recorded spot" via bounding-box + UTM Euclidean distance; there is no containment concept.

Two additional Madrid Open Data sources were investigated and confirmed usable:
- **`SER_BANDA_APARCAMIENTO`** (shapefile, `shape_type = 3` / PolyLine): 87,608 curb-band line segments in EPSG:25830 (ETRS89 UTM 30N — the same CRS the app already works in). Fields: `ID` (internal GIS feature id, not a zone number), `Color` (same taxonomy as `MadridZoneType`, plus `"Gris"` for non-SER bands), `Res_NumPla` (spot count). Filtering out `Gris` leaves 34,459 bands — close to the current `ser_zones` row count, confirming this is the geometric sibling of the data already ingested.
- **`200075` callejero CSV** (the dataset previously used, then retired in `2026-06-27-replace-ser-source-with-colour-data` for lacking colour): still useful here as the *only* available source of the administrative `zone_number` (`Zona Servicio Estacionamiento Regulado`, e.g. `"163"`), street name, and district per address point.

Neither source is a closed zone-boundary polygon by itself. This design combines them: buffer+dissolve the band lines into polygons, and spatially join them to the callejero to recover the administrative zone identity.

The purpose of the resulting polygon is strictly to answer "is this vehicle's GPS position inside a SER zone" and "which zone number is it" — not to model individual parking bay geometry. That framing (confirmed with the user) simplifies several decisions below: precise per-bay geometry (parking orientation, exact bay depth) is not needed, since GPS positioning error already dwarfs that level of precision.

## Goals / Non-Goals

**Goals:**
- `SerZone` becomes a bureaucratic zone (`zone_number` + `zone_type`), not a point or a single band
- `SerZone.contains(location) -> bool` is a real, boundary-inclusive point-in-polygon check
- Ingestion combines both sources without introducing PostGIS
- Preserve the existing truncate-reload ingestion strategy and the `CityParkingDataProvider` port shape (no port-level redesign needed — D1 from the prior change already made the port opaque enough to absorb a multi-source pipeline inside one provider)
- Keep the bulk zone-list query (used for map rendering, potentially hundreds of rows) light by not carrying street names on every row

**Non-Goals:**
- Wiring the "vehicle inside a SER zone" notification (`SerZoneTriggerHandler`) — follow-up change, consumes `contains()` once it exists
- Zone-number-level exceptions (schedules, resident permits) — future; this change only makes the geometry and administrative identity real
- PostGIS / GeoAlchemy2 adoption — deferred; row counts after dissolve are small enough (see D5) that in-Python `shapely` checks are sufficient
- Multi-city support — Madrid remains the only implementation
- Modelling individual parking-bay orientation/geometry (parallel vs perpendicular) — not needed for a zone-containment check; see D4

## Decisions

### D1 — New domain value object `SerZoneBoundaryRecord` replaces `ParkingSpotRecord`

**Chosen**: `SerZoneBoundaryRecord` (frozen dataclass), an **ingestion-time** value object: `zone_number: str`, `zone_type: str`, `district: str`, `street_names: list[str]`, `spot_count: int`, `geometry: shapely.Polygon | shapely.MultiPolygon` (in EPSG:25830 metres). `ParkingSpotRecord` is deleted, not deprecated. `street_names` here is transient — it exists only to let the ingestion use case populate the separate `ser_zone_streets` table (see D9); it is not the same thing as the query-time `SerZone` entity, which does not carry street names (see D9).

**Why**: The record no longer represents a point/spot — carrying the old name forward would repeat the exact naming fiction the `SerZoneRecord → ParkingSpotRecord` rename fixed in the prior change. `shapely` geometry as a domain field follows existing precedent: `domain/value_objects/location.py` already imports `pyproj` directly for `distance_m`, so a geometry library in the domain value-objects layer is not a new kind of dependency, just a new one.

**Alternative considered**: Keep `ParkingSpotRecord` and add optional geometry fields — rejected; it would carry meaningless point fields (`latitude`/`longitude`/`utm_x`/`utm_y`) that no longer describe anything real.

---

### D2 — `CityParkingDataProvider` port is unchanged; only its return type changes; new provider is `MadridSerStreetsProvider`

**Chosen**: The ABC keeps `city_code: str` and `get_records() -> list[T]` exactly as-is; `T` changes from `ParkingSpotRecord` to `SerZoneBoundaryRecord`. The Madrid provider's `get_records()` internally fetches and combines *two* URLs instead of one. The new concrete class is named `MadridSerStreetsProvider` (English-only naming, replacing the old `MadridSerCallesProvider` — "Calles" mixed Spanish into an otherwise-English codebase; "Streets" keeps the class name fully English while still reflecting that it resolves zone identity via street/address data).

**Why**: Validates the original D1 decision from `replace-ser-source-with-colour-data`: "different cities might use REST APIs, FTP files, or proprietary feeds — keeping the pipeline opaque behind one method gives each provider full control." A provider needing two source files is exactly the kind of case that design already anticipated.

---

### D3 — Spatial join: `shapely.strtree.STRtree`, no new heavy geo dependency

**Chosen**: Build an `STRtree` over the callejero address points that are themselves SER-zoned (reprojected once to UTM 25830) at ingestion time — of the 215,203 total callejero rows, roughly 142,000 carry `Zona Servicio Estacionamiento Regulado == "000"` ("not part of any SER zone") and are excluded from the index entirely; only the remaining ~73,000 SER-zoned points are indexed. For each of the 34,459 SER bands, query the tree for the nearest (SER-zoned) callejero point using the band's midpoint, and inherit that point's `zone_number`, street name, and district.

**Why**: A naive O(bands × addresses) scan is ~7.4 billion comparisons — impractical. `STRtree` ships inside `shapely` (already being added for buffering/dissolve/containment), so no separate spatial-index dependency (e.g. `scipy.spatial.cKDTree`) is needed. Excluding `"000"` rows from the index is load-bearing, not optional: including them lets a band's "nearest callejero point" resolve to a nearby non-SER building (statistically likely, since ~66% of all addresses are `"000"`) instead of the correct SER-zoned address, which was caught in manual verification against live data — most bands were being misattributed to a bogus `zone_number="000"` group, starving real zones down to one or two bands each and producing near-single-band-sized (visually rectangular) dissolved polygons instead of the true district-spanning shape.

**Alternative considered**: Coarse UTM grid bucketing implemented by hand — rejected; `STRtree` is a maintained, correct implementation already available for free once `shapely` is a dependency.

---

### D4 — Buffer bands into polygons using one uniform half-width; parking orientation is not modelled

**Chosen**: Buffer every retained band's polyline with a single fixed half-width (proposed default **2.5 m**, i.e. a 5 m-wide strip), regardless of parking orientation. Group the resulting polygons by `(zone_number, zone_type)` and apply `shapely.ops.unary_union` to dissolve each group into one `SerZone`'s geometry (a `Polygon` or `MultiPolygon` — zones are frequently physically discontinuous, which is expected, not a bug).

**Why**: The only question this polygon needs to answer is "is a vehicle's GPS position inside this SER zone" — a coarse containment check, not a model of individual parking-bay geometry. Differentiating parallel vs perpendicular bay width would imply a precision the input doesn't warrant: consumer GPS positioning error routinely exceeds several metres, well past the difference between a 2.2 m parallel strip and a 5 m perpendicular bay. A single generous width sized toward the larger case avoids manufacturing false confidence from a distinction (`Bateria_Li`) that doesn't change the answer to the question being asked. `Bateria_Li` is therefore not parsed at all — it is unused.

**Alternative considered**: Orientation-aware half-widths (`Línea` vs `Batería`) — rejected per the above; adds parsing complexity and an extra field dependency for a precision gain that doesn't matter to the containment decision.

---

### D5 — No PostGIS; geometry stored as WKT text, containment computed in Python; no bounding-box prefilter needed

**Chosen**: Add a `geometry_wkt TEXT` column (EPSG:25830, matching the CRS buffering happens in). `find_containing`/`find_nearest` load **all** zone rows via `list_all()` and run `shapely.wkt.loads()` + `.covers()`/`.distance()` in Python — no SQL bounding-box prefilter.

**Why**: Dissolving ~34,459 bands by `(zone_number, zone_type)` collapses the row count to on the order of a few hundred zone records (Madrid has roughly 100-300 numbered SER zones, times a handful of colour splits at most) — two orders of magnitude smaller than today's 34,519 point rows. A full in-memory scan over a few hundred `shapely` geometries per request is well within acceptable latency for this app's scale (self-hosted, low request volume; see prior design docs' "home LAN" framing) and avoids maintaining a second index (bbox columns) alongside the geometry itself.

**Alternative considered**: PostGIS `geometry` column + `ST_Contains`/GiST index — rejected for this change; more "correct" at large scale but a real infra addition (extension, `GeoAlchemy2`, docker image change) that the current row count doesn't justify. Revisit if zone count or query volume grows enough to matter.

**Alternative considered**: Keep the old WGS84 lat/lng bounding-box columns as a prefilter — rejected; adds schema and index complexity for a table now two orders of magnitude smaller.

---

### D6 — Canonical geometry stored in UTM 25830; reprojected to WGS84 only at the API boundary

**Chosen**: Buffering and dissolve happen in UTM metres (consistent units for `.buffer()`); `geometry_wkt` is stored in EPSG:25830. `GET /parking/ser-zone` and `GET /parking/ser-zones` reproject to WGS84 GeoJSON at serialization time, reusing the existing `Transformer.from_crs("EPSG:25830", "EPSG:4326", ...)` pattern already present in the Madrid provider.

**Why**: Buffer widths are defined in metres; doing that math in WGS84 degrees would require constant reprojection or produce distorted (non-circular) buffers. Keeping one canonical CRS in storage avoids ambiguity about which representation is authoritative.

---

### D7 — `pyshp` added for shapefile parsing instead of hand-rolled binary parsing

**Chosen**: Add `pyshp` (pure Python, no GDAL/system dependency) to read `.shp`/`.dbf`.

**Why**: The SHP/DBF binary formats were parsed by hand (via `struct`) during exploration to avoid installing anything, but that approach is not something to ship in production ingestion code — it's undocumented, easy to get subtly wrong, and `pyshp` is a small, maintained, pure-Python library with no GDAL requirement, consistent with this project's preference for self-hosted-friendly dependencies (same reasoning that avoided `fiona`/`geopandas`/PostGIS elsewhere in this design).

---

### D8 — `ser_zones` table rework: drop point columns, add zone identity + geometry, no street names on this table

**Chosen**: Alembic migration drops `latitude`, `longitude`, `utm_x`, `utm_y`; adds `zone_number VARCHAR(10) NOT NULL`, `district TEXT NOT NULL`, `geometry_wkt TEXT NOT NULL`. Add a `UNIQUE (zone_number, zone_type)` constraint. Keep `spot_count INTEGER NOT NULL DEFAULT -1` and the truncate-reload ingestion strategy. Street names are **not** a column here — see D9.

**Why**: Matches this project's established precedent (`replace-ser-source-with-colour-data` D6) of additive-columns + drop-what's-no-longer-meaningful, accepting a breaking change given truncate-reload means no data loss either direction.

---

### D9 — Street names normalized into a separate `ser_zone_streets` table, joined only on single-zone lookups

**Chosen**: A new table `ser_zone_streets (id SERIAL PK, zone_number VARCHAR(10) NOT NULL, zone_type VARCHAR(50) NOT NULL, street_name TEXT NOT NULL)`, with an index on `(zone_number, zone_type)`. `SerZoneRepository` gets a new method `get_street_names(zone_number: str, zone_type: str) -> list[str]`, called only where a single zone's detail is needed. The `SerZone` query-time domain entity does **not** carry a `street_names` field — it stays `zone_number`, `zone_type`, `district`, `spot_count`, `geometry`. `GET /parking/ser-zone` (single-coordinate lookup) calls `get_street_names` at the router level after resolving the zone, and includes the result in its response. `GET /parking/ser-zones` (bulk, used for map rendering — every stored zone at once) and the frontend map tooltip do **not** include street names at all.

**Why**: A zone can legitimately span many streets, and `GET /parking/ser-zones` returns every zone in the city in one response for map rendering — carrying a variable-length street list on every one of those few hundred rows is unnecessary weight on the one endpoint that fires most often and needs to stay light. `GET /parking/ser-zone` returns exactly one row, so joining street names there is cheap and directly useful (it's the endpoint that answers "what zone am I in," where naming the streets is part of a useful answer). Normalizing into its own table also means street names never distort `ser_zones`' row size or the truncate-reload bulk insert.

**Alternative considered**: Keep `street_names TEXT[]` inline on `ser_zones` — rejected per the above; also considered and rejected: fetching street names lazily on map-tooltip hover via a per-zone network call — rejected as unnecessary complexity and poor UX (a hover firing a network request) for information the tooltip doesn't need to show.

---

### D10 — Simplify dissolved zone geometry before storage; round coordinate precision at the API boundary

**Chosen**: After `unary_union` dissolves a zone's buffered bands (D4), apply `shapely.simplify(tolerance=0.5, preserve_topology=True)` (metres, in the UTM 25830 storage CRS) to the result before constructing the `SerZoneBoundaryRecord`. Separately, at the API boundary (`geojson.py`), snap reprojected WGS84 coordinates to a fixed precision (~6 decimal degrees, ≈0.1m) before building the GeoJSON response, via `shapely.set_precision()`.

**Why**: Discovered against live Madrid data (not caught by synthetic test fixtures, which were far smaller than reality): an unsimplified dissolved zone can have hundreds of disconnected polygon parts and tens of thousands of coordinate points each — one real zone (151/Verde) measured at 936 parts, 72,630 coordinates, contributing 3.6MB of WKT alone; the full bulk `GET /parking/ser-zones` response measured 74MB total. This is impractical for a browser to fetch, parse, and render, and is far more precision than the pipeline actually has: the buffer half-width itself (D4) is only a 2.5m estimate, and GPS positioning error dominates precision at the scale this data is used for (see D4's reasoning). A 0.5m simplification tolerance was measured (against the same live zone) to cut coordinate count ~7x (72,630 → 10,277) while preserving 97.9% of the original polygon area — a shape difference invisible at any web-map zoom level a user would actually view.

**Alternative considered**: Reduce `buffer()`'s `quad_segs` (round-cap/join fidelity) instead of simplifying the dissolved result — rejected as insufficient alone; the dominant vertex-count driver is the sheer number of unioned band parts (hundreds per zone), not per-band arc fidelity, so simplifying the final dissolved shape is the correct lever. Coordinate-precision rounding at the API boundary is a complementary, independent saving (shrinks JSON text size per point) and doesn't substitute for reducing point count.

---

## Risks / Trade-offs

- **The 2.5 m buffer half-width is an estimate, not a verified Madrid regulation figure** → Mitigation: a named constant (not a magic number scattered in code), documented as approximate, revisited after visually inspecting rendered polygons on the map (this change includes real polygon rendering, making mis-sized bands easy to spot). Deliberately sized generously since GPS error, not bay geometry, is the binding constraint on precision (see D4).
- **Nearest-neighbour join can mis-attribute a band to the wrong `zone_number`** near a boundary where the zone number changes mid-block → Mitigation: accept as an approximation; the callejero's per-address-number granularity (215k points) is finer than per-street, which already minimises this compared to a per-street join.
- **A `(zone_number, zone_type)` dissolve can still cross real block/street boundaries** if band geometry is sparse in some area, producing a coarser polygon than reality → Mitigation: none planned for this change; acceptable given this is already a large accuracy improvement over point+radius.
- **Two external URLs must both succeed for an ingestion run** (SHP zip + callejero CSV) → Mitigation: carry forward the existing failure-handling requirement — any fetch/parse failure aborts the run and leaves existing data intact (same as today's single-source behaviour).
- **`shapely` and `pyshp` are new dependencies** → Mitigation: both are pure-Python (or ship prebuilt wheels with no GDAL/system library requirement), consistent with this project's self-hosted deployment constraints; no docker image changes needed.
- **Breaking API and DB changes, no versioning strategy** → Consistent with this project's established early-stage precedent; document breaking changes in the PR description.

## Migration Plan

1. Add `shapely` and `pyshp` to `pyproject.toml`
2. Alembic migration: drop `latitude`/`longitude`/`utm_x`/`utm_y` from `ser_zones`; add `zone_number`, `district`, `geometry_wkt`, unique `(zone_number, zone_type)`; create `ser_zone_streets` table with an index on `(zone_number, zone_type)`
3. Implement callejero CSV parsing (zone number, street, district, DMS→decimal lat/lng) as a focused internal helper
4. Implement `MadridSerStreetsProvider`: fetch+unzip the SHP, parse bands, fetch+parse the callejero, spatially join (`STRtree`), buffer with the uniform half-width, dissolve, and return `SerZoneBoundaryRecord`s
5. Update `IngestCityParkingData` to persist `SerZoneBoundaryRecord`s into both `ser_zones` and `ser_zone_streets` within the same truncate-reload transaction
6. Update `SerZone` domain entity (`contains()` method, no `street_names` field) and `SerZoneRepository` (`find_containing`, reworked `find_nearest`, `list_all`, new `get_street_names`)
7. Update `GET /parking/ser-zone` (includes street names via `get_street_names`) and `GET /parking/ser-zones` (no street names) response schemas — breaking; reproject UTM → WGS84 GeoJSON at the boundary
8. Update the frontend map component to render polygons (`react-leaflet` `Polygon`/`GeoJSON`) with tooltip content excluding street names; update Playwright e2e assertions
9. Set `SER_ZONE_SHP_URL` / `MADRID_CALLEJERO_URL` in deployment env (both have sensible defaults, so no forced action before deploy)
10. Deploy; first scheduled ingestion run populates the new schema

**Rollback**: Revert the application deploy and run the inverse Alembic migration (drop new columns and the `ser_zone_streets` table, re-add the old point columns). No data-loss risk in either direction since ingestion is truncate-reload — the next run under whichever code version is active simply repopulates the tables.
