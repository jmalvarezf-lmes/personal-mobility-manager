### Requirement: CityParkingDataProvider abstract port
The system SHALL define a `CityParkingDataProvider` abstract base class in the domain ports layer (`domain/ports/city_parking_data_provider.py`). It SHALL declare one abstract property `city_code: str` and one abstract method `get_records() -> list[SerZoneBoundaryRecord]`. All city-specific ingestion logic (fetching, parsing, transforming) SHALL live inside concrete provider implementations; the port itself SHALL import only domain types.

#### Scenario: Port defines contract for any city provider
- **WHEN** a new city provider class inherits from `CityParkingDataProvider`
- **THEN** it must implement `city_code` and `get_records()` to be instantiable

#### Scenario: Use case depends only on the port
- **WHEN** `IngestCityParkingData` is constructed
- **THEN** it accepts any `CityParkingDataProvider` instance without importing any city-specific class

---

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

---

### Requirement: ZoneType abstract class defines the city zone-type contract
The system SHALL define a `ZoneType` abstract base class in `domain/value_objects/zone_type.py` with two abstract members: an abstract property `display_name: str` (the validated string stored in DB and returned in the API) and an abstract classmethod `from_raw(cls, raw: str) -> ZoneType | None` (parses the city-specific raw source value and returns `None` for unrecognised values). Each city's `CityParkingDataProvider` implementation SHALL provide a concrete `ZoneType` subclass. The provider SHALL call `from_raw()` during parsing and SHALL skip any row where it returns `None`, logging a warning with the unrecognised raw value.

#### Scenario: Known zone type validated and stored
- **WHEN** the source row for Madrid contains `"043000255 Azul"` and `MadridZoneType.from_raw("Azul")` returns `MadridZoneType.Azul`
- **THEN** `SerZoneBoundaryRecord.zone_type` is `"Azul"` (the `display_name` of the returned instance)

#### Scenario: Unknown zone type skips the row
- **WHEN** the source row has a zone type string that `from_raw()` cannot map to any known member
- **THEN** the row is skipped, a warning is logged with the unrecognised value, and the skipped-row counter is incremented

#### Scenario: Each city's zone types are independent
- **WHEN** a second city defines a `ZoneType` subclass with different members (e.g., `Blue`, `Yellow`)
- **THEN** its subclass is self-contained and does not affect `MadridZoneType` or the `ZoneType` abstract class in the domain

#### Scenario: Abstract class enforces implementation contract
- **WHEN** a new city provider inherits from `ZoneType` without implementing `display_name` or `from_raw`
- **THEN** calling the unimplemented method raises `NotImplementedError`

---

### Requirement: MadridZoneType implements ZoneType for Madrid's five classifications
The system SHALL provide `MadridZoneType` in `infrastructure/parking_services/madrid/zone_type.py` as a concrete subclass of `ZoneType` (implemented as a `str, Enum`) with members: `Azul = "Azul"`, `Verde = "Verde"`, `AltaRotacion = "Alta Rotación"`, `Naranja = "Naranja"`, `Rojo = "Rojo"`. Its `display_name` SHALL return the enum's string value. Its `from_raw(raw)` classmethod SHALL attempt to match `raw` against member values and return the matching member or `None`.

#### Scenario: from_raw maps known name to member
- **WHEN** `MadridZoneType.from_raw("Azul")` is called
- **THEN** it returns `MadridZoneType.Azul`

#### Scenario: from_raw returns None for unknown value
- **WHEN** `MadridZoneType.from_raw("Purple")` is called
- **THEN** it returns `None`

---

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

---

### Requirement: Provider registry maps city code to provider instance
The system SHALL maintain a provider registry (a dict `city_code -> CityParkingDataProvider`) populated at application startup. The `ENABLED_CITIES` environment variable (default: `"madrid"`) SHALL control which city codes are active. Only providers whose `city_code` appears in `ENABLED_CITIES` SHALL be instantiated and registered.

#### Scenario: Default config activates Madrid only
- **WHEN** `ENABLED_CITIES` is unset
- **THEN** only `MadridSerStreetsProvider` is registered

#### Scenario: Unknown city code is ignored with a warning
- **WHEN** `ENABLED_CITIES` contains a city code with no registered implementation
- **THEN** the application logs a warning and starts normally without that city

#### Scenario: Multiple cities can be enabled simultaneously
- **WHEN** `ENABLED_CITIES=madrid,barcelona` and a `BarcelonaProvider` exists
- **THEN** both providers are registered and scheduled independently
