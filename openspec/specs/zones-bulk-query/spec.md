## ADDED Requirements

### Requirement: Bulk zones endpoint returns all zones for a city
The API SHALL expose `GET /parking/ser-zones` accepting a required `city` query parameter. When `city=madrid` it SHALL return all SER zones currently stored in the database as a JSON object with a `city` string field and a `zones` array. Each zone entry SHALL include `zone_number`, `zone_type`, `colour`, `district`, `spot_count`, and `geometry` (a GeoJSON `Polygon` or `MultiPolygon` in WGS84). Street names SHALL NOT be included in this response — this endpoint returns every stored zone at once and street names are only fetched on a per-zone basis (see `ser-zone-query`'s `GET /parking/ser-zone`).

#### Scenario: Successful bulk query for Madrid
- **WHEN** a GET request is made to `/parking/ser-zones?city=madrid`
- **THEN** the response status is 200 and the body contains `{ "city": "madrid", "zones": [...] }` where each element has `zone_number`, `zone_type`, `colour`, `district`, `spot_count`, `geometry`, and no `street_names` field

#### Scenario: Unknown city returns 404
- **WHEN** a GET request is made to `/parking/ser-zones?city=barcelona` (not yet supported)
- **THEN** the response status is 404 with a detail message indicating the city is not supported

#### Scenario: Empty dataset returns empty list
- **WHEN** a GET request is made to `/parking/ser-zones?city=madrid` and no zones are stored
- **THEN** the response status is 200 and `zones` is an empty array `[]`

#### Scenario: colour field matches domain ZoneType.colour
- **WHEN** a zone with `zone_type = "Azul"` is returned
- **THEN** its `colour` field equals `"#2563EB"`

#### Scenario: geometry is reprojected to WGS84 GeoJSON
- **WHEN** a zone's stored `geometry_wkt` is in EPSG:25830
- **THEN** the API response's `geometry` field is valid GeoJSON in WGS84 (EPSG:4326) coordinates

#### Scenario: geometry coordinates are rounded to a bounded precision
- **WHEN** a zone's geometry is reprojected to WGS84 for this response
- **THEN** coordinate values are rounded to approximately 6 decimal degrees (~0.1m), avoiding the full float64 decimal expansion, to keep the bulk response's JSON payload size practical for every zone returned at once

### Requirement: Config endpoint exposes OSM tile URL
The API SHALL expose `GET /config` returning a JSON object with an `osm_tile_url` field whose value is read from the `OSM_TILE_URL` environment variable. If the variable is not set, the field SHALL be `null`.

#### Scenario: OSM_TILE_URL is set
- **WHEN** `OSM_TILE_URL=http://tiles.local:8080/tile/{z}/{x}/{y}.png` and a GET request is made to `/config`
- **THEN** the response is `{ "osm_tile_url": "http://tiles.local:8080/tile/{z}/{x}/{y}.png" }`

#### Scenario: OSM_TILE_URL is not set
- **WHEN** `OSM_TILE_URL` is not present in the environment and a GET request is made to `/config`
- **THEN** the response is `{ "osm_tile_url": null }`
