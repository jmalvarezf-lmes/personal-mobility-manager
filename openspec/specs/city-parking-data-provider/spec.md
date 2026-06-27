### Requirement: CityParkingDataProvider abstract port
The system SHALL define a `CityParkingDataProvider` abstract base class in the domain ports layer (`domain/ports/city_parking_data_provider.py`). It SHALL declare one abstract property `city_code: str` and one abstract method `get_records() -> list[ParkingSpotRecord]`. All city-specific ingestion logic (fetching, parsing, transforming) SHALL live inside concrete provider implementations; the port itself SHALL import only domain types.

#### Scenario: Port defines contract for any city provider
- **WHEN** a new city provider class inherits from `CityParkingDataProvider`
- **THEN** it must implement `city_code` and `get_records()` to be instantiable

#### Scenario: Use case depends only on the port
- **WHEN** `IngestCityParkingData` is constructed
- **THEN** it accepts any `CityParkingDataProvider` instance without importing any city-specific class

---

### Requirement: ParkingSpotRecord domain value object
The system SHALL define `ParkingSpotRecord` as a frozen dataclass in the domain value objects layer with fields: `street_name: str`, `zone_type: str`, `latitude: float`, `longitude: float`, `utm_x: float`, `utm_y: float`, `spot_count: int`. The `zone_type` field holds the `display_name` of the city-specific `ZoneType` subclass (always a valid, validated string). The `spot_count` field uses the sentinel value `-1` to indicate that the source data did not include spot count information; zero is NOT used as a sentinel. This replaces the infrastructure-scoped `SerZoneRecord`.

#### Scenario: Record created by any city provider
- **WHEN** any concrete `CityParkingDataProvider.get_records()` returns a list
- **THEN** each element is a `ParkingSpotRecord` with all fields populated; `zone_type` holds the validated zone type display name; `spot_count` is `-1` if the source did not include a spot count

#### Scenario: Spot count unknown is -1 not zero
- **WHEN** the source data has no spot count for a parking address
- **THEN** `ParkingSpotRecord.spot_count` is `-1`, not `0`

#### Scenario: Record is immutable
- **WHEN** code attempts to mutate a field on a `ParkingSpotRecord`
- **THEN** a `FrozenInstanceError` is raised (frozen dataclass enforcement)

---

### Requirement: ZoneType abstract class defines the city zone-type contract
The system SHALL define a `ZoneType` abstract base class in `domain/value_objects/zone_type.py` with two abstract members: an abstract property `display_name: str` (the validated string stored in DB and returned in the API) and an abstract classmethod `from_raw(cls, raw: str) -> ZoneType | None` (parses the city-specific raw source value and returns `None` for unrecognised values). Each city's `CityParkingDataProvider` implementation SHALL provide a concrete `ZoneType` subclass. The provider SHALL call `from_raw()` during parsing and SHALL skip any row where it returns `None`, logging a warning with the unrecognised raw value.

#### Scenario: Known zone type validated and stored
- **WHEN** the source row for Madrid contains `"043000255 Azul"` and `MadridZoneType.from_raw("Azul")` returns `MadridZoneType.Azul`
- **THEN** `ParkingSpotRecord.zone_type` is `"Azul"` (the `display_name` of the returned instance)

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

### Requirement: MadridSerCallesProvider concrete implementation
The system SHALL provide `MadridSerCallesProvider` in the infrastructure layer (`infrastructure/parking_services/madrid/ser_calles_provider.py`). It SHALL implement `CityParkingDataProvider` with `city_code = "madrid"`. Its `get_records()` method SHALL fetch the 218228 CSV from the URL read from the `MADRID_SER_CALLES_URL` environment variable (default: the official Madrid Open Data URL), decode as Latin-1, parse all rows, and return a list of `ParkingSpotRecord`.

#### Scenario: Fetch and parse returns records
- **WHEN** `MadridSerCallesProvider.get_records()` is called and the URL is reachable
- **THEN** it returns a non-empty list of `ParkingSpotRecord` with `city_code = "madrid"`

#### Scenario: HTTP failure raises an exception
- **WHEN** the HTTP request returns a non-2xx status or network error
- **THEN** `get_records()` raises an exception; the caller (use case) logs the failure and aborts the ingestion run without mutating stored data

#### Scenario: Configurable URL
- **WHEN** `MADRID_SER_CALLES_URL` env var is set
- **THEN** `MadridSerCallesProvider` uses that URL instead of the default

---

### Requirement: Provider registry maps city code to provider instance
The system SHALL maintain a provider registry (a dict `city_code -> CityParkingDataProvider`) populated at application startup. The `ENABLED_CITIES` environment variable (default: `"madrid"`) SHALL control which city codes are active. Only providers whose `city_code` appears in `ENABLED_CITIES` SHALL be instantiated and registered.

#### Scenario: Default config activates Madrid only
- **WHEN** `ENABLED_CITIES` is unset
- **THEN** only `MadridSerCallesProvider` is registered

#### Scenario: Unknown city code is ignored with a warning
- **WHEN** `ENABLED_CITIES` contains a city code with no registered implementation
- **THEN** the application logs a warning and starts normally without that city

#### Scenario: Multiple cities can be enabled simultaneously
- **WHEN** `ENABLED_CITIES=madrid,barcelona` and a `BarcelonaProvider` exists
- **THEN** both providers are registered and scheduled independently
