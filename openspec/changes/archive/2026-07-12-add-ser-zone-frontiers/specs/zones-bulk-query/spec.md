## MODIFIED Requirements

### Requirement: Bulk zones endpoint returns all zones for a city
The API SHALL expose `GET /parking/ser-zones` accepting a required `city` query parameter. When `city=madrid` it SHALL return all SER zones currently stored in the database as a JSON object with a `city` string field, a `zones` array, and a `frontiers` array. Each `zones` entry SHALL include `zone_number`, `zone_type`, `colour`, `district`, `spot_count`, and `geometry` (a GeoJSON `Polygon` or `MultiPolygon` in WGS84) — unchanged from before. Each `frontiers` entry SHALL include `zone_number`, `neighbourhood`, and `geometry` (the real Madrid Barrios administrative boundary polygon, reprojected to WGS84 GeoJSON) — one entry per stored `ser_zone_areas` row, independent of how many colours that zone_number has in `zones`. Street names SHALL NOT be included in either array — this endpoint returns every stored zone/frontier at once and street names are only fetched on a per-zone basis (see `ser-zone-query`'s `GET /parking/ser-zone`).

#### Scenario: Successful bulk query for Madrid
- **WHEN** a GET request is made to `/parking/ser-zones?city=madrid`
- **THEN** the response status is 200 and the body contains `{ "city": "madrid", "zones": [...], "frontiers": [...] }` where each `zones` element has `zone_number`, `zone_type`, `colour`, `district`, `spot_count`, `geometry`, and no `street_names` field, and each `frontiers` element has `zone_number`, `neighbourhood`, `geometry`, and no `colour`/`zone_type`/`street_names` field

#### Scenario: Unknown city returns 404
- **WHEN** a GET request is made to `/parking/ser-zones?city=barcelona` (not yet supported)
- **THEN** the response status is 404 with a detail message indicating the city is not supported

#### Scenario: Empty dataset returns empty lists
- **WHEN** a GET request is made to `/parking/ser-zones?city=madrid` and no zones are stored
- **THEN** the response status is 200 and both `zones` and `frontiers` are empty arrays `[]`

#### Scenario: colour field matches domain ZoneType.colour
- **WHEN** a zone with `zone_type = "Azul"` is returned
- **THEN** its `colour` field equals `"#2563EB"`

#### Scenario: geometry is reprojected to WGS84 GeoJSON
- **WHEN** a zone's stored `geometry_wkt` is in EPSG:25830
- **THEN** the API response's `geometry` field is valid GeoJSON in WGS84 (EPSG:4326) coordinates

#### Scenario: geometry coordinates are rounded to a bounded precision
- **WHEN** a zone's geometry is reprojected to WGS84 for this response
- **THEN** coordinate values are rounded to approximately 6 decimal degrees (~0.1m), avoiding the full float64 decimal expansion, to keep the bulk response's JSON payload size practical for every zone returned at once

#### Scenario: frontiers array has one entry per zone_number, not per zone_type
- **WHEN** a zone_number has three `zones` entries (one per colour)
- **THEN** the `frontiers` array still has exactly one entry for that zone_number

#### Scenario: Two zone_numbers sharing the same barrio return identical frontier geometry
- **WHEN** two different zone_numbers both resolve to the same official barrio
- **THEN** both zone_numbers appear as separate `frontiers` entries with identical `geometry` — this is expected, not deduplicated
