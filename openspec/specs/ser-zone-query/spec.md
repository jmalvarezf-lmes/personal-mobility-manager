### Requirement: Coordinate-based SER zone lookup endpoint
The system SHALL expose a REST endpoint `GET /parking/ser-zone` that accepts `lat` and `lng` query parameters and returns the SER zone information for the nearest zone boundary to the given coordinate (zero distance if the point is inside a zone). Because this endpoint resolves exactly one zone, its response SHALL include that zone's street names (fetched via `SerZoneRepository.get_street_names`).

#### Scenario: Valid coordinates return zone info
- **WHEN** a `GET /parking/ser-zone?lat=40.4168&lng=-3.7038` request is made and the database has data
- **THEN** the response is HTTP 200 with a JSON body containing `zone_number`, `zone_type`, `district`, `street_names`, `spot_count`, and `distance_meters`

#### Scenario: Missing parameters return 422
- **WHEN** a request is made with `lat` or `lng` missing
- **THEN** the response is HTTP 422 with a JSON error describing the missing parameter

#### Scenario: Invalid coordinate values return 422
- **WHEN** `lat` is outside [-90, 90] or `lng` is outside [-180, 180]
- **THEN** the response is HTTP 422 with a validation error message

#### Scenario: Empty database returns 404
- **WHEN** the database has no rows in `ser_zones` and a valid query is made
- **THEN** the response is HTTP 404 with `{"detail": "No SER zone data available"}`

#### Scenario: Point inside a zone returns zero distance
- **WHEN** the query coordinate falls inside a stored zone's polygon
- **THEN** `distance_meters` is `0` and the containing zone is returned

---

### Requirement: Nearest-zone search by distance to polygon geometry, full-table scan
The system SHALL find the nearest zone by loading all `SerZone` records via the repository's `list_all()`, converting the query point's WGS84 lat/lng to UTM 25830, and computing the exact distance from the point to each zone's polygon geometry (zero if inside), returning the record with the minimum distance. No SQL bounding-box prefilter is used, since the post-dissolve row count is small enough for a full in-memory scan.

#### Scenario: Nearest zone returned
- **WHEN** at least one `SerZone` row exists
- **THEN** the row with the minimum distance-to-polygon from the query point is returned

#### Scenario: Distance returned in response
- **WHEN** a nearest zone is found
- **THEN** `distance_meters` in the response contains the UTM distance rounded to the nearest integer, computed against the polygon geometry

---

### Requirement: Domain SerZone entity
The system SHALL model SER zone data as a `SerZone` domain entity (Python dataclass) with fields: `zone_number: str`, `zone_type: str`, `district: str`, `spot_count: int`, `geometry: shapely.geometry.base.BaseGeometry`. It SHALL expose a `contains(location: GeoLocation) -> bool` method that performs a boundary-inclusive point-in-polygon check (using `shapely`'s `covers()` semantics, not the boundary-exclusive `contains()`) against `geometry`, reprojecting `location` to the geometry's CRS (EPSG:25830) before testing. `SerZone` does NOT carry street names — see `SerZoneRepository.get_street_names` below.

#### Scenario: SerZone created from repository result
- **WHEN** the `SerZoneRepository` returns a result
- **THEN** a `SerZone` instance is constructed with `zone_number`, `zone_type`, `district`, `spot_count`, and `geometry` populated, without any infrastructure imports beyond the geometry library

#### Scenario: contains() returns True for a point inside the polygon
- **WHEN** `zone.contains(location)` is called with a `GeoLocation` that falls within `zone.geometry`
- **THEN** it returns `True`

#### Scenario: contains() returns True for a point exactly on the boundary
- **WHEN** `zone.contains(location)` is called with a `GeoLocation` that falls exactly on `zone.geometry`'s edge
- **THEN** it returns `True` (boundary-inclusive, via `covers()`)

#### Scenario: contains() returns False for a point outside the polygon
- **WHEN** `zone.contains(location)` is called with a `GeoLocation` outside `zone.geometry`
- **THEN** it returns `False`

---

### Requirement: SerZoneRepository port
The system SHALL define a `SerZoneRepository` abstract port in the domain layer with methods `find_nearest(location: GeoLocation) -> SerZone | None`, `find_containing(location: GeoLocation) -> SerZone | None`, `list_all() -> list[SerZone]`, and `get_street_names(zone_number: str, zone_type: str) -> list[str]`.

#### Scenario: Port implemented by PostgreSQL adapter
- **WHEN** the PostgreSQL `SerZoneRepository` is injected into a use case
- **THEN** it satisfies the `SerZoneRepository` ABC without the use case knowing it is PostgreSQL

#### Scenario: find_containing returns the zone whose polygon contains the point
- **WHEN** `find_containing(location)` is called and one stored zone's geometry contains `location`
- **THEN** that `SerZone` is returned

#### Scenario: find_containing returns None when no zone contains the point
- **WHEN** `find_containing(location)` is called and no stored zone's geometry contains `location`
- **THEN** `None` is returned

#### Scenario: get_street_names returns all streets for one zone
- **WHEN** `get_street_names(zone_number, zone_type)` is called for a zone with three stored streets
- **THEN** it returns a list of all three street names

#### Scenario: get_street_names is not called by list_all or find_nearest/find_containing
- **WHEN** `list_all()`, `find_nearest()`, or `find_containing()` are called
- **THEN** no query against `ser_zone_streets` is made; street names are only fetched via an explicit `get_street_names` call

#### Scenario: Port is dependency-injected
- **WHEN** a use case depending on `SerZoneRepository` is constructed
- **THEN** it accepts a `SerZoneRepository` instance as a constructor argument (no global state)

---

### Requirement: FindNearestSerZone use case
The system SHALL implement a `FindNearestSerZone` application use case that accepts a `GeoLocation`, validates bounds, delegates to `SerZoneRepository.find_nearest`, and returns a `SerZone` or raises `SerZoneNotFoundError`. It does NOT fetch street names — that composition happens at the API layer for endpoints that need it.

#### Scenario: Valid location returns SerZone
- **WHEN** `FindNearestSerZone.execute(location)` is called with a valid Madrid-area GeoLocation
- **THEN** it returns a `SerZone` domain entity

#### Scenario: Not found raises domain error
- **WHEN** `find_nearest` returns `None`
- **THEN** `FindNearestSerZone` raises `SerZoneNotFoundError` (domain exception, no HTTP concepts)

---

### Requirement: FindContainingSerZone use case
The system SHALL implement a `FindContainingSerZone` application use case that accepts a `GeoLocation`, delegates to `SerZoneRepository.find_containing`, and returns a `SerZone | None` (no exception on not-found, since "not inside any zone" is a valid, expected outcome rather than an error).

#### Scenario: Location inside a zone returns that SerZone
- **WHEN** `FindContainingSerZone.execute(location)` is called with a location inside a stored zone
- **THEN** it returns that `SerZone` domain entity

#### Scenario: Location outside all zones returns None
- **WHEN** `FindContainingSerZone.execute(location)` is called with a location not inside any stored zone
- **THEN** it returns `None` without raising an exception

---

### Requirement: OpenAPI documentation
The system SHALL expose interactive API documentation at `/docs` (Swagger UI) automatically via FastAPI.

#### Scenario: Docs endpoint accessible
- **WHEN** a `GET /docs` request is made to the running API
- **THEN** the response is HTTP 200 with the Swagger UI HTML page
