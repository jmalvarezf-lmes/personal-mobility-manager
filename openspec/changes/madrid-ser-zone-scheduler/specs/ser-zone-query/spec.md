## ADDED Requirements

### Requirement: Coordinate-based SER zone lookup endpoint
The system SHALL expose a REST endpoint `GET /parking/ser-zone` that accepts `lat` and `lng` query parameters and returns the SER zone information for the nearest street in the database.

#### Scenario: Valid coordinates return zone info
- **WHEN** a `GET /parking/ser-zone?lat=40.4168&lng=-3.7038` request is made and the database has data
- **THEN** the response is HTTP 200 with a JSON body containing `street_name`, `zone_code`, `zone_label`, `distance_meters`, `latitude`, and `longitude`

#### Scenario: Missing parameters return 422
- **WHEN** a request is made with `lat` or `lng` missing
- **THEN** the response is HTTP 422 with a JSON error describing the missing parameter

#### Scenario: Invalid coordinate values return 422
- **WHEN** `lat` is outside [-90, 90] or `lng` is outside [-180, 180]
- **THEN** the response is HTTP 422 with a validation error message

#### Scenario: Empty database returns 404
- **WHEN** the database has no rows in `ser_zones` and a valid query is made
- **THEN** the response is HTTP 404 with `{"detail": "No SER zone data available"}`

---

### Requirement: Nearest-street search using bounding box + Haversine
The system SHALL find the nearest street by first filtering candidates within a configurable bounding box (default: ±0.01 degrees, ~1km), then computing Haversine distance in Python and returning the record with the minimum distance.

#### Scenario: Result within bounding box
- **WHEN** a query point has at least one `ser_zones` row within ±0.01 degrees
- **THEN** the nearest row by Haversine distance is returned

#### Scenario: No result in bounding box expands search
- **WHEN** no rows exist within ±0.01 degrees of the query point
- **THEN** the system expands the bounding box by 2× and retries once; if still no result, returns HTTP 404

#### Scenario: Distance returned in response
- **WHEN** a nearest street is found
- **THEN** `distance_meters` in the response contains the Haversine distance rounded to the nearest integer

---

### Requirement: Domain SerZone entity
The system SHALL model SER zone data as a `SerZone` domain entity (pure Python dataclass) with fields: `street_name: str`, `zone_code: str`, `zone_label: str`, `location: GeoLocation`.

#### Scenario: SerZone created from repository result
- **WHEN** the `SerZoneRepository` returns a result
- **THEN** a `SerZone` instance is constructed without any infrastructure imports

---

### Requirement: SerZoneRepository port
The system SHALL define a `SerZoneRepository` abstract port in the domain layer with a method `find_nearest(location: GeoLocation, radius_deg: float) -> SerZone | None`.

#### Scenario: Port implemented by PostgreSQL adapter
- **WHEN** the PostgreSQL `SerZoneRepository` is injected into the use case
- **THEN** it satisfies the `SerZoneRepository` ABC without the use case knowing it is PostgreSQL

#### Scenario: Port is dependency-injected
- **WHEN** the `FindNearestSerZone` use case is constructed
- **THEN** it accepts a `SerZoneRepository` instance as a constructor argument (no global state)

---

### Requirement: FindNearestSerZone use case
The system SHALL implement a `FindNearestSerZone` application use case that accepts a `GeoLocation`, validates bounds, delegates to `SerZoneRepository.find_nearest`, and returns a `SerZone` or raises `SerZoneNotFoundError`.

#### Scenario: Valid location returns SerZone
- **WHEN** `FindNearestSerZone.execute(location)` is called with a valid Madrid-area GeoLocation
- **THEN** it returns a `SerZone` domain entity

#### Scenario: Not found raises domain error
- **WHEN** `find_nearest` returns `None`
- **THEN** `FindNearestSerZone` raises `SerZoneNotFoundError` (domain exception, no HTTP concepts)

---

### Requirement: OpenAPI documentation
The system SHALL expose interactive API documentation at `/docs` (Swagger UI) automatically via FastAPI.

#### Scenario: Docs endpoint accessible
- **WHEN** a `GET /docs` request is made to the running API
- **THEN** the response is HTTP 200 with the Swagger UI HTML page
