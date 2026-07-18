## MODIFIED Requirements

### Requirement: Domain SerZone entity
The system SHALL model SER zone data as a `SerZone` domain entity (Python dataclass) with fields: `city_code: str`, `zone_number: str`, `zone_type: str`, `district: str`, `spot_count: int`, `geometry: shapely.geometry.base.BaseGeometry`. It SHALL expose a `contains(location: GeoLocation) -> bool` method that performs a boundary-inclusive point-in-polygon check (using `shapely`'s `covers()` semantics, not the boundary-exclusive `contains()`) against `geometry`, reprojecting `location` to the geometry's CRS (EPSG:25830) before testing. `SerZone` does NOT carry street names — see `SerZoneRepository.get_street_names` below. `city_code` identifies which city's enforcement schedule and holiday calendar apply to this zone (see the `ser-enforcement-schedule` and `public-holiday-calendar` capabilities).

#### Scenario: SerZone created from repository result
- **WHEN** the `SerZoneRepository` returns a result
- **THEN** a `SerZone` instance is constructed with `city_code`, `zone_number`, `zone_type`, `district`, `spot_count`, and `geometry` populated, without any infrastructure imports beyond the geometry library

#### Scenario: contains() returns True for a point inside the polygon
- **WHEN** `zone.contains(location)` is called with a `GeoLocation` that falls within `zone.geometry`
- **THEN** it returns `True`

#### Scenario: contains() returns True for a point exactly on the boundary
- **WHEN** `zone.contains(location)` is called with a `GeoLocation` that falls exactly on `zone.geometry`'s edge
- **THEN** it returns `True` (boundary-inclusive, via `covers()`)

#### Scenario: contains() returns False for a point outside the polygon
- **WHEN** `zone.contains(location)` is called with a `GeoLocation` outside `zone.geometry`
- **THEN** it returns `False`

### Requirement: SerZoneRepository port
The system SHALL define a `SerZoneRepository` abstract port in the domain layer with methods `find_nearest(location: GeoLocation) -> SerZone | None`, `find_containing(location: GeoLocation) -> SerZone | None`, `list_all() -> list[SerZone]`, `get_street_names(city_code: str, zone_number: str, zone_type: str) -> list[str]`, `get_zone_area(city_code: str, zone_number: str) -> ZoneArea | None`, and `list_zone_areas() -> list[ZoneArea]`.

#### Scenario: Port implemented by PostgreSQL adapter
- **WHEN** the PostgreSQL `SerZoneRepository` is injected into a use case
- **THEN** it satisfies the `SerZoneRepository` ABC without the use case knowing it is PostgreSQL

#### Scenario: find_containing returns the zone whose polygon contains the point
- **WHEN** `find_containing(location)` is called and one stored zone's geometry contains `location`
- **THEN** that `SerZone` is returned, with its `city_code` populated

#### Scenario: find_containing returns None when no zone contains the point
- **WHEN** `find_containing(location)` is called and no stored zone's geometry contains `location`
- **THEN** `None` is returned

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

### Requirement: ZoneArea domain value object
The system SHALL define `ZoneArea` as a frozen dataclass in the domain layer with fields: `city_code: str`, `zone_number: str`, `neighbourhood: str`, `geometry: shapely.geometry.base.BaseGeometry` (the frontier polygon or multi-polygon — a real Madrid Barrios administrative boundary, in EPSG:25830 metres). `ZoneArea` is a query-time read model distinct from `SerZone` — it exists at `(city_code, zone_number)` grain, not `(zone_number, zone_type)` grain, and carries no `zone_type`, `spot_count`, or containment behaviour. `city_code` disambiguates `zone_number` values that may collide across cities.

#### Scenario: ZoneArea is immutable
- **WHEN** code attempts to mutate a field on a `ZoneArea`
- **THEN** a `FrozenInstanceError` is raised (frozen dataclass enforcement)

#### Scenario: ZoneArea carries no containment method
- **WHEN** inspecting the `ZoneArea` class
- **THEN** it has no `contains()` method or equivalent — frontier geometry is presentation-only and is never used for containment checks

#### Scenario: Two cities' ZoneArea rows sharing a zone_number are distinguishable
- **WHEN** `list_zone_areas()` returns entries for two different cities that happen to share the same `zone_number`
- **THEN** each entry's `city_code` field identifies which city it belongs to
