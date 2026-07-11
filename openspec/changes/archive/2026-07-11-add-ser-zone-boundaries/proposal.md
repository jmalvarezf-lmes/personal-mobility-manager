## Why

`ser_zones` currently stores one point per parking spot (nearest-point lookup only), which can answer "what colour is probably here" but not "is this vehicle actually inside a regulated zone" — the question that matters for ticket liability. Madrid publishes a real curb-band geometry source (`SER_BANDA_APARCAMIENTO`, a polyline shapefile) and the existing callejero address directory carries the administrative zone number that the band geometry lacks. Combining them lets `SerZone` become a true bureaucratic zone with a real polygon boundary, enabling a genuine point-in-polygon containment check instead of a nearest-point approximation.

## What Changes

- Add a Madrid SER zone boundary shapefile source: download+unzip `SER_ZONE_SHP_URL` (default `https://geoportal.madrid.es/fsdescargas/IDEAM_WBGEOPORTAL/MOVILIDAD/ZONA_SER/SHP_ZIP.zip`), parse `SER_BANDA_APARCAMIENTO.shp`/`.dbf` (curb-band polylines with `Color` and `Res_NumPla`; `Bateria_Li` orientation is not used — see below), filter out `Color == "Gris"` (non-SER bands)
- Add the callejero CSV as a second Madrid source: download `MADRID_CALLEJERO_URL` (default `https://datos.madrid.es/dataset/200075-0-callejero/resource/200075-1-callejero-csv/download/200075-1-callejero-csv.csv`), used only to look up `zone_number` (`Zona Servicio Estacionamiento Regulado`), street name, and district per address point
- Spatially join each curb band to its nearest callejero address point *that is itself SER-zoned* (UTM 25830, reusing the existing WGS84↔UTM transform pattern) to inherit `zone_number`, street name, and district. Callejero rows with `Zona Servicio Estacionamiento Regulado == "000"` (Madrid's code for "not in a SER zone" — roughly two-thirds of all address rows) are excluded from the join candidate set entirely; including them would let bands frequently snap to a nearby non-SER building instead of the correct zone, fragmenting real zones into near-single-band slivers
- Buffer each band polyline into a polygon using a single fixed half-width (parking orientation is not modelled — a zone-containment check only needs to know "is the vehicle near this curb," not the precise bay geometry, and GPS positioning error already exceeds the difference between orientations), then dissolve (union) all same-`(zone_number, zone_type)` band polygons into one `SerZone` row's geometry — **BREAKING**: a zone number that mixes colours now yields multiple `SerZone` rows (one per colour), not one
- Replace the point-based `ParkingSpotRecord` domain value object with a zone-boundary-shaped record carrying `zone_number`, `zone_type`, `district`, `street_names`, `spot_count`, and geometry — **BREAKING**
- Add `SerZone.contains(location: GeoLocation) -> bool`, a real, boundary-inclusive point-in-polygon domain method (via `shapely`'s `covers()`), replacing the informal "nearest point within a radius" approximation
- Add `SerZoneRepository.find_containing(location) -> SerZone | None`; keep `find_nearest` for proximity/map use cases but redefine its distance metric against zone geometry (nearest polygon) instead of a stored point
- Rework the `ser_zones` table: drop single-point `latitude`/`longitude`/`utm_x`/`utm_y` as the primary shape, add `zone_number`, `district`, and a `geometry` column (WKT text, no PostGIS); given the row count after dissolve is small (a few hundred), no bounding-box prefilter is needed — **BREAKING** (migration, truncate-reload retained)
- **BREAKING**: Normalize street names into a new `ser_zone_streets` table (one row per zone/street pair) instead of an inline array column on `ser_zones` — a zone can span many streets, and the bulk zone-list endpoint (used for map rendering, every zone at once) shouldn't carry that weight on every row. Street names are only fetched on demand via a new `SerZoneRepository.get_street_names()`, used solely by the single-coordinate lookup endpoint
- Update `GET /parking/ser-zone` (single-coordinate lookup) response shape to expose `zone_number`, `district`, `street_names`, and `distance_meters` — **BREAKING**
- Update `GET /parking/ser-zones` (bulk list) response shape to expose `zone_number`, `district`, and polygon geometry, with no street names — **BREAKING**
- Update the frontend map to render zone polygons (`react-leaflet` `Polygon`/`GeoJSON`) instead of point `CircleMarker`s, with tooltips showing zone number, district, and spot count (no street names, to avoid a per-hover network call)
- Give `MadridZoneType`'s three remaining variants (`AltaRotacion`, `Naranja`, `Rojo`) their own distinct colours instead of collapsing them all to grey — **BREAKING** (colour values in the API response change for those three zone types). This was left as grey in an earlier change when zone geometry didn't exist yet and the distinction wasn't visually actionable; now that real per-zone polygons render on the map, showing all five zone types distinctly is the point
- Simplify each dissolved zone's final geometry (`shapely.simplify()`, boundary-inclusive-preserving) before storage, and round GeoJSON coordinate precision at the API boundary — discovered against live Madrid data: unsimplified geometry produced a 74MB bulk-endpoint payload (one zone alone: 936 polygon parts, 72,630 coordinate points), which is impractical for a browser to parse/render. A 0.5m simplification tolerance cuts coordinate count ~7x while preserving ~98% of the original area — well within the precision the 2.5m buffer estimate already gives up
- Add `shapely` (buffering, dissolve/union, point-in-polygon) and `pyshp` (shapefile parsing) as new dependencies; no PostGIS

**Out of scope**: wiring `SerZoneTriggerHandler` to send a "vehicle inside a SER zone" notification (a separate follow-up change that will consume `SerZone.contains()`), zone-number-level exceptions (schedules, resident permits), and PostGIS adoption.

## Capabilities

### New Capabilities
_None — this change remodels existing capabilities; no new capability is introduced._

### Modified Capabilities
- `city-parking-data-provider`: `ParkingSpotRecord` is replaced by a zone-boundary value object carrying geometry; `MadridZoneType.from_raw()` now parses the SHP's plain `Color` field (no RGB prefix) instead of the CSV's `color` field; the Madrid provider's `get_records()` pipeline now fetches and joins two sources instead of one
- `ser-zone-ingestion`: dual-source download (SHP zip + callejero CSV), spatial join, buffer + dissolve into zone boundaries; `ser_zones` table schema changes; new env vars `SER_ZONE_SHP_URL` and `MADRID_CALLEJERO_URL`
- `ser-zone-query`: `SerZone` entity reshaped to bureaucratic-zone granularity with a `contains()` method; `SerZoneRepository` gains `find_containing()`; `find_nearest` redefined against polygon geometry; `GET /parking/ser-zone` response shape changes
- `zones-bulk-query`: `GET /parking/ser-zones` response shape changes to expose zone number, district, street list, and polygon geometry instead of a single point
- `osm-zone-map`: frontend renders zone polygons instead of point markers; tooltip content updated accordingly
- `zone-colour`: `AltaRotacion`, `Naranja`, and `Rojo` get distinct hex colours instead of all falling back to grey

## Impact

- `pyproject.toml`: add `shapely`, `pyshp`
- Alembic migration: rework `ser_zones` table columns, add new `ser_zone_streets` table
- `infrastructure/parking_services/madrid/`: rewritten/renamed provider(s), new shapefile parsing, new callejero parsing, spatial join + dissolve logic
- `domain/value_objects/`: replace `ParkingSpotRecord`; `SerZone` entity gains geometry + `contains()`
- `domain/ports/ser_zone_repository.py`, `infrastructure/repositories/postgres/ser_zone_repo.py`: new `find_containing`, reworked `find_nearest`, reworked storage/query
- `presentation/api/routers/parking.py`, `zones.py`, `presentation/api/schemas.py`: breaking response shape changes
- `frontend/`: map component moves from `CircleMarker` to polygon rendering; Playwright e2e updates
- Existing tests across ingestion, repository, and API layers need substantial rewrites to match the new shape
