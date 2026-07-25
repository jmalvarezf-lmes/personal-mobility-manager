## MODIFIED Requirements

### Requirement: Domain SerZone entity
The system SHALL model SER zone data as a `SerZone` domain entity (Python dataclass) with fields: `city_code: str`, `zone_number: str`, `zone_type: str`, `district: str`, `spot_count: int`, `geometry: shapely.geometry.base.BaseGeometry`. It SHALL expose a `contains(location: GeoLocation, tolerance_m: float = 0.0) -> bool` method that returns `True` if `location` (reprojected to the geometry's CRS, EPSG:25830) is covered by `geometry` (boundary-inclusive, using `shapely`'s `covers()` semantics, not the boundary-exclusive `contains()`) OR is within `tolerance_m` metres of `geometry`'s boundary (`geometry.distance(point) <= tolerance_m`). `tolerance_m` defaults to `0.0`, preserving exact zero-tolerance boundary-inclusive behavior for any caller that omits it. `SerZone` does NOT carry street names — see `SerZoneRepository.get_street_names` below. `city_code` identifies which city's enforcement schedule and holiday calendar apply to this zone (see the `ser-enforcement-schedule` and `public-holiday-calendar` capabilities).

#### Scenario: SerZone created from repository result
- **WHEN** the `SerZoneRepository` returns a result
- **THEN** a `SerZone` instance is constructed with `city_code`, `zone_number`, `zone_type`, `district`, `spot_count`, and `geometry` populated, without any infrastructure imports beyond the geometry library

#### Scenario: contains() returns True for a point inside the polygon
- **WHEN** `zone.contains(location)` is called with a `GeoLocation` that falls within `zone.geometry`
- **THEN** it returns `True`

#### Scenario: contains() returns True for a point exactly on the boundary
- **WHEN** `zone.contains(location)` is called with a `GeoLocation` that falls exactly on `zone.geometry`'s edge
- **THEN** it returns `True` (boundary-inclusive, via `covers()`)

#### Scenario: contains() returns False for a point outside the polygon and outside any tolerance
- **WHEN** `zone.contains(location)` is called with a `GeoLocation` outside `zone.geometry` and either `tolerance_m` is omitted (defaults to `0.0`) or the location is farther from `zone.geometry` than the given `tolerance_m`
- **THEN** it returns `False`

#### Scenario: contains() returns True for a point outside the polygon but within tolerance_m
- **WHEN** `zone.contains(location, tolerance_m=X)` is called with a `GeoLocation` whose distance to `zone.geometry` is greater than zero but less than or equal to `X`
- **THEN** it returns `True`

---

### Requirement: SerZoneRepository port
The system SHALL define a `SerZoneRepository` abstract port in the domain layer with methods `find_nearest(location: GeoLocation) -> SerZone | None`, `find_containing(location: GeoLocation) -> SerZone | None`, `list_all() -> list[SerZone]`, `get_street_names(city_code: str, zone_number: str, zone_type: str) -> list[str]`, `get_zone_area(city_code: str, zone_number: str) -> ZoneArea | None`, and `list_zone_areas() -> list[ZoneArea]`. The concrete PostgreSQL implementation's `find_containing()` SHALL apply the configurable containment tolerance (see "Configurable SER zone containment tolerance" below) to every zone it checks, so any caller reaching zone resolution through `find_containing()` — directly or via an application-layer use case — receives the tolerant check without needing to pass a tolerance itself. `find_nearest()`'s distance calculation is unaffected by this tolerance.

#### Scenario: Port implemented by PostgreSQL adapter
- **WHEN** the PostgreSQL `SerZoneRepository` is injected into a use case
- **THEN** it satisfies the `SerZoneRepository` ABC without the use case knowing it is PostgreSQL

#### Scenario: find_containing returns the zone whose polygon contains the point
- **WHEN** `find_containing(location)` is called and one stored zone's geometry contains `location`
- **THEN** that `SerZone` is returned, with its `city_code` populated

#### Scenario: find_containing returns None when no zone contains the point, even within tolerance
- **WHEN** `find_containing(location)` is called and no stored zone's geometry contains `location` and no zone's geometry is within the configured tolerance of `location`
- **THEN** `None` is returned

#### Scenario: find_containing returns a zone whose polygon boundary is within the configured tolerance of the point
- **WHEN** `find_containing(location)` is called and `location` is outside every stored zone's geometry but within the configured containment tolerance of one zone's boundary
- **THEN** that `SerZone` is returned

#### Scenario: find_containing applies the same tolerance regardless of caller
- **WHEN** `find_containing(location)` is called either via `FindContainingSerZone` (application use case) or directly by an infrastructure caller (e.g. `ElParkingSerTicketProvider`)
- **THEN** both receive an identical tolerant result — the tolerance is applied once, inside the repository implementation, not per caller

#### Scenario: get_street_names returns all streets for one zone in one city
- **WHEN** `get_street_names(city_code, zone_number, zone_type)` is called for a zone with three stored streets under that `city_code`
- **THEN** it returns a list of all three street names

#### Scenario: get_street_names does not return another city's streets for the same zone_number/zone_type
- **WHEN** `get_street_names(city_code, zone_number, zone_type)` is called and another city has stored streets under the same `zone_number`/`zone_type` pair
- **THEN** only that `city_code`'s streets are returned

#### Scenario: get_zone_area returns the neighbourhood and frontier for one city's zone_number
- **WHEN** `get_zone_area(city_code, zone_number)` is called for a `(city_code, zone_number)` pair with a stored `ser_zone_areas` row
- **THEN** it returns a `ZoneArea` with that pair's `neighbourhood` and frontier `geometry`

#### Scenario: get_zone_area returns None for an unknown city_code/zone_number pair
- **WHEN** `get_zone_area(city_code, zone_number)` is called for a pair with no `ser_zone_areas` row
- **THEN** it returns `None`

#### Scenario: list_zone_areas returns all stored frontiers
- **WHEN** `list_zone_areas()` is called
- **THEN** it returns one `ZoneArea` per row in `ser_zone_areas`, across all cities

#### Scenario: get_street_names, get_zone_area, and list_zone_areas are not called by list_all or find_nearest/find_containing
- **WHEN** `list_all()`, `find_nearest()`, or `find_containing()` are called
- **THEN** no query against `ser_zone_streets` or `ser_zone_areas` is made; that data is only fetched via its own explicit method call

#### Scenario: Port is dependency-injected
- **WHEN** a use case depending on `SerZoneRepository` is constructed
- **THEN** it accepts a `SerZoneRepository` instance as a constructor argument (no global state)

## ADDED Requirements

### Requirement: Configurable SER zone containment tolerance
The system SHALL expose a `get_ser_zone_containment_tolerance_cm() -> int` function in `config.py` that reads the `SER_ZONE_CONTAINMENT_TOLERANCE_CM` environment variable as an integer number of centimetres, defaulting to `50` when unset or non-integer. This is a technical/operational setting (compensating for GPS positioning error), not a per-user preference, and is not exposed through any user-facing API or preference storage. `PostgresSerZoneRepository.find_containing()` SHALL convert this value to metres (`/ 100`) before passing it as `SerZone.contains()`'s `tolerance_m` argument.

#### Scenario: Default tolerance applies when the environment variable is unset
- **WHEN** `SER_ZONE_CONTAINMENT_TOLERANCE_CM` is not set in the environment
- **THEN** `get_ser_zone_containment_tolerance_cm()` returns `50`

#### Scenario: Environment variable overrides the default
- **WHEN** `SER_ZONE_CONTAINMENT_TOLERANCE_CM` is set to a valid integer string
- **THEN** `get_ser_zone_containment_tolerance_cm()` returns that integer

#### Scenario: Invalid value falls back to the default
- **WHEN** `SER_ZONE_CONTAINMENT_TOLERANCE_CM` is set to a non-integer string
- **THEN** `get_ser_zone_containment_tolerance_cm()` returns `50`

#### Scenario: Not exposed as a user preference
- **WHEN** inspecting `GET/PUT /preferences` or any other user-facing preference endpoint
- **THEN** no field for SER zone containment tolerance exists — it is only configurable via the `SER_ZONE_CONTAINMENT_TOLERANCE_CM` environment variable
