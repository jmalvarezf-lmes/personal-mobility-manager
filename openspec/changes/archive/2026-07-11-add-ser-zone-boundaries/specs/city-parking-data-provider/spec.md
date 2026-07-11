## REMOVED Requirements

### Requirement: ParkingSpotRecord domain value object
**Reason**: `ParkingSpotRecord` represented a single point (one parking spot), which no longer reflects what a `CityParkingDataProvider` returns once `SerZone` becomes a bureaucratic zone with a real polygon boundary. Replaced by `SerZoneBoundaryRecord`.
**Migration**: Any code constructing or consuming `ParkingSpotRecord` must migrate to `SerZoneBoundaryRecord` (see ADDED Requirements below). Ingestion is truncate-reload, so the next scheduled ingestion run populates the new shape directly with no data migration needed.

### Requirement: MadridSerCallesProvider concrete implementation
**Reason**: Replaced by `MadridSerStreetsProvider`, which combines the SER band shapefile and the callejero CSV into zone-boundary records instead of fetching a single point-based CSV. The new name is also fully English (the old name mixed in the Spanish "Calles").
**Migration**: `MADRID_SER_CALLES_URL` is replaced by `SER_ZONE_SHP_URL` and `MADRID_CALLEJERO_URL`. The provider registry constructs `MadridSerStreetsProvider` in place of `MadridSerCallesProvider`.

## ADDED Requirements

### Requirement: SerZoneBoundaryRecord domain value object
The system SHALL define `SerZoneBoundaryRecord` as a frozen dataclass in the domain value objects layer with fields: `zone_number: str`, `zone_type: str`, `district: str`, `street_names: list[str]`, `spot_count: int`, `geometry: shapely.geometry.base.BaseGeometry` (a `Polygon` or `MultiPolygon` in EPSG:25830 metres). This replaces `ParkingSpotRecord`. This is an ingestion-time record only — `street_names` exists so the ingestion use case can populate the separate `ser_zone_streets` table; it is not carried on the query-time `SerZone` entity.

#### Scenario: Record created by the Madrid provider
- **WHEN** `MadridSerStreetsProvider.get_records()` returns a list
- **THEN** each element is a `SerZoneBoundaryRecord` with `zone_type` set to a validated `MadridZoneType.display_name`, `geometry` a valid `shapely` `Polygon` or `MultiPolygon`, and `spot_count` the sum of all bands dissolved into that record

#### Scenario: Spot count unknown is -1 not zero
- **WHEN** none of the bands dissolved into a `SerZoneBoundaryRecord` have a known spot count
- **THEN** `spot_count` is `-1`, not `0`

#### Scenario: Record is immutable
- **WHEN** code attempts to mutate a field on a `SerZoneBoundaryRecord`
- **THEN** a `FrozenInstanceError` is raised (frozen dataclass enforcement)

#### Scenario: Multiple street names preserved
- **WHEN** a dissolved zone spans bands originally matched to more than one distinct street name via the callejero join
- **THEN** `street_names` contains all distinct street names, not just one

### Requirement: MadridSerStreetsProvider combines two Madrid sources into zone boundaries
The system SHALL provide `MadridSerStreetsProvider` in the infrastructure layer, implementing `CityParkingDataProvider` with `city_code = "madrid"`. Its `get_records()` method SHALL: (1) download and unzip the SER band shapefile from `SER_ZONE_SHP_URL`, parse `SER_BANDA_APARCAMIENTO.shp`/`.dbf`, and discard rows where `Color == "Gris"`; (2) download and parse the callejero CSV from `MADRID_CALLEJERO_URL`, decoded as Latin-1; (3) spatially join each retained band to its nearest callejero address point (by UTM 25830 distance) to obtain `zone_number`, street name, and district; (4) buffer each band's geometry by a single fixed half-width (parking orientation is not used — see design.md D4); (5) group by `(zone_number, zone_type)` and dissolve each group's polygons into one `SerZoneBoundaryRecord`.

#### Scenario: Fetch and parse returns zone boundary records
- **WHEN** `MadridSerStreetsProvider.get_records()` is called and both URLs are reachable
- **THEN** it returns a non-empty list of `SerZoneBoundaryRecord` with `city_code = "madrid"`, one record per distinct `(zone_number, zone_type)` combination found

#### Scenario: Non-SER bands are excluded
- **WHEN** a band's `Color` field is `"Gris"`
- **THEN** that band is excluded from every downstream zone boundary

#### Scenario: All retained bands use the same buffer width regardless of orientation
- **WHEN** any retained band is buffered into a polygon
- **THEN** the same fixed half-width constant is used, independent of the band's parking orientation

#### Scenario: Bands sharing a zone number and colour are dissolved into one record
- **WHEN** multiple bands are matched to the same `zone_number` and the same `zone_type`
- **THEN** they produce a single `SerZoneBoundaryRecord` whose geometry is the union of their buffered polygons and whose `spot_count` is their summed spot counts

#### Scenario: A zone number with mixed colours produces multiple records
- **WHEN** bands matched to the same `zone_number` have more than one distinct `zone_type`
- **THEN** one `SerZoneBoundaryRecord` is produced per distinct `zone_type` present, all sharing the same `zone_number`, `district`, and overlapping `street_names`

#### Scenario: HTTP failure on either source raises an exception
- **WHEN** the shapefile download or the callejero CSV download returns a non-2xx status or a network error occurs
- **THEN** `get_records()` raises an exception; the caller (ingestion use case) logs the failure and aborts the ingestion run without mutating stored data

#### Scenario: Configurable URLs
- **WHEN** `SER_ZONE_SHP_URL` or `MADRID_CALLEJERO_URL` env vars are set
- **THEN** `MadridSerStreetsProvider` uses those URLs instead of the defaults
