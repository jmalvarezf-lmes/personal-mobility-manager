## MODIFIED Requirements

### Requirement: SerZoneRepository port
The system SHALL define a `SerZoneRepository` abstract port in the domain layer with methods `find_nearest(location: GeoLocation) -> SerZone | None`, `find_containing(location: GeoLocation) -> SerZone | None`, `find_all_containing(location: GeoLocation) -> list[SerZone]`, `list_all() -> list[SerZone]`, `get_street_names(city_code: str, zone_number: str, zone_type: str) -> list[str]`, `get_zone_area(city_code: str, zone_number: str) -> ZoneArea | None`, and `list_zone_areas() -> list[ZoneArea]`. The concrete PostgreSQL implementation's `find_containing()` and `find_all_containing()` SHALL both apply the configurable containment tolerance (see "Configurable SER zone containment tolerance" below) to every zone they check, so any caller reaching zone resolution through either method — directly or via an application-layer use case — receives the tolerant check without needing to pass a tolerance itself. `find_containing()` SHALL be equivalent to `find_all_containing(location)[0] if candidates else None` — the first zone in iteration order among every candidate `find_all_containing()` would return, preserving its exact existing single-result behavior for all of its current callers. `find_nearest()`'s distance calculation is unaffected by this tolerance.

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

#### Scenario: find_all_containing returns every tolerance-matching zone
- **WHEN** `find_all_containing(location)` is called and two stored zones' geometries each either contain `location` or are within the configured tolerance of it
- **THEN** both `SerZone` records are returned, in the same iteration order `find_containing()` would use to pick its single result

#### Scenario: find_all_containing returns an empty list when nothing matches
- **WHEN** `find_all_containing(location)` is called and no stored zone's geometry contains or is within tolerance of `location`
- **THEN** an empty list is returned

#### Scenario: find_containing and find_all_containing agree on the primary zone
- **WHEN** both `find_containing(location)` and `find_all_containing(location)` are called for the same `location`
- **THEN** `find_containing(location)` equals `find_all_containing(location)[0]` (or `None` when the list is empty)

#### Scenario: get_street_names, get_zone_area, and list_zone_areas are not called by list_all or find_nearest/find_containing
- **WHEN** `list_all()`, `find_nearest()`, `find_containing()`, or `find_all_containing()` are called
- **THEN** no query against `ser_zone_streets` or `ser_zone_areas` is made; that data is only fetched via its own explicit method call

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

#### Scenario: Port is dependency-injected
- **WHEN** a use case depending on `SerZoneRepository` is constructed
- **THEN** it accepts a `SerZoneRepository` instance as a constructor argument (no global state)
