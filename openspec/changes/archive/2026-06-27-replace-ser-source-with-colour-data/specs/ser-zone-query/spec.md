## MODIFIED Requirements

### Requirement: Coordinate-based SER zone lookup endpoint
The system SHALL expose a REST endpoint `GET /parking/ser-zone` that accepts `lat` and `lng` query parameters and returns the SER zone information for the nearest parking spot in the database.

#### Scenario: Valid coordinates return zone info
- **WHEN** a `GET /parking/ser-zone?lat=40.4168&lng=-3.7038` request is made and the database has data
- **THEN** the response is HTTP 200 with a JSON body containing `street_name`, `zone_type`, `spot_count`, `distance_meters`, `latitude`, and `longitude`

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

### Requirement: Domain SerZone entity
The system SHALL model SER zone data as a `SerZone` domain entity (pure Python dataclass) with fields: `street_name: str`, `zone_type: str`, `spot_count: int`, `location: GeoLocation`.

#### Scenario: SerZone created from repository result
- **WHEN** the `SerZoneRepository` returns a result
- **THEN** a `SerZone` instance is constructed with `zone_type` (the validated display name) and `spot_count` populated, without any infrastructure imports

## REMOVED Requirements

### Requirement: zone_code and zone_label in API response
**Reason**: The 218228 SER Calles source has no numeric zone code. Colour replaces zone_label as the human-readable zone identifier; zone_code had no semantic value beyond being a repeat of zone_label.
**Migration**: API consumers MUST update to use `zone_type` instead of `zone_label`/`zone_code`. For Madrid, the `zone_type` values are: `"Azul"`, `"Verde"`, `"Alta Rotación"`, `"Naranja"`, `"Rojo"`.
