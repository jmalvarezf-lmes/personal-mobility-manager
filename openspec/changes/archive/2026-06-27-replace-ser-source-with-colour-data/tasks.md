## 1. Domain Layer

- [x] 1.1 Create `ZoneType` abstract base class in `domain/value_objects/zone_type.py` with abstract property `display_name: str` and abstract classmethod `from_raw(cls, raw: str) -> ZoneType | None`
- [x] 1.2 Add `ParkingSpotRecord` frozen dataclass to `domain/value_objects/parking_spot_record.py` with fields: `street_name: str`, `zone_type: str`, `latitude: float`, `longitude: float`, `utm_x: float`, `utm_y: float`, `spot_count: int` — `zone_type` holds the `display_name` of the validated zone type; `spot_count = -1` signals unknown, never use `0` as a sentinel
- [x] 1.3 Update `SerZone` entity in `domain/entities/ser_zone.py`: add `zone_type: str` and `spot_count: int`, remove `zone_code` and `zone_label`
- [x] 1.4 Create `CityParkingDataProvider` ABC in `domain/ports/city_parking_data_provider.py` with abstract property `city_code: str` and abstract method `get_records() -> list[ParkingSpotRecord]`

## 2. DB Schema Migration

- [x] 2.1 Update `ser_zones` SQLAlchemy table definition in `infrastructure/orm/tables.py`: add `zone_type` (String, not-null), add `spot_count` (Integer, not-null, server_default="-1"), remove `zone_code` and `zone_label` columns
- [x] 2.2 Generate Alembic migration with `alembic revision --autogenerate -m "add-zone-type-spot-count-drop-zone-code-label"` and verify the generated script adds `zone_type VARCHAR(50) NOT NULL DEFAULT ''` + `spot_count INTEGER NOT NULL DEFAULT -1` and drops `zone_code` + `zone_label`

## 3. Madrid SER Calles Provider

- [x] 3.1 Define `MadridZoneType(ZoneType, str, Enum)` in `infrastructure/parking_services/madrid/zone_type.py` with members `Azul = "Azul"`, `Verde = "Verde"`, `AltaRotacion = "Alta Rotación"`, `Naranja = "Naranja"`, `Rojo = "Rojo"`; implement `display_name` returning `self.value` and `from_raw(raw)` trying `cls(raw)` and returning `None` on `ValueError`
- [x] 3.2 Create `MadridSerCallesProvider` in `infrastructure/parking_services/madrid/ser_calles_provider.py` implementing `CityParkingDataProvider` with `city_code = "madrid"`; the constructor reads `MADRID_SER_CALLES_URL` from env (with a sensible default pointing to the official Madrid Open Data URL)
- [x] 3.3 Implement `get_records()` in `MadridSerCallesProvider`: fetch CSV via HTTP (Latin-1 decode), parse semicolon-delimited rows, extract `calle`, raw CSV `color` column (strip 9-digit RGB prefix with `color_field.split(" ", 1)[1]` to get plain name, then call `MadridZoneType.from_raw()` — skip row with warning if `None`), `gis_x` + `gis_y` (use directly as metres, no ÷100), and `numero_plazas` (use `-1` if field is absent, empty, or non-numeric — do NOT skip the row); store `zone_type.display_name` in `ParkingSpotRecord.zone_type`; reproject UTM to WGS84 via pyproj; apply Madrid bounding-box validation; return `list[ParkingSpotRecord]`
- [x] 3.4 Delete `infrastructure/parking_services/madrid/csv_parser.py` (`CallejeroCsvParser`) and remove its imports from any module that references it

## 4. Repository and Application Use Case

- [x] 4.1 Update `SerZonePostgresRepository` in `infrastructure/repositories/postgres/ser_zone_repo.py`: bulk-insert `zone_type` and `spot_count`, remove `zone_code`/`zone_label` from INSERT and SELECT; map `zone_type` and `spot_count` when constructing `SerZone` entities
- [x] 4.2 Update `SerZoneRepository` port in `domain/ports/ser_zone_repository.py` if the interface references `zone_code` or `zone_label` — remove those from the return type contract
- [x] 4.3 Refactor `IngestSerZones` use case in `application/use_cases/ingest_ser_zones.py` to accept a `CityParkingDataProvider` via constructor injection instead of a Madrid-specific class; replace the parsing call with `provider.get_records()` and map `ParkingSpotRecord` → repository insert
- [x] 4.4 Update `FindNearestSerZone` use case in `application/use_cases/find_nearest_ser_zone.py` to pass `zone_type` and `spot_count` when constructing the returned `SerZone`

## 5. Presentation and Config

- [x] 5.1 Update the Pydantic response model in `presentation/api/routers/parking.py`: add `zone_type: str` and `spot_count: int`; remove `zone_code` and `zone_label`
- [x] 5.2 Update the router handler to read `ser_zone.zone_type` and `ser_zone.spot_count` from the entity and populate the response
- [x] 5.3 Add provider registry to `infrastructure/parking_services/provider_registry.py`: reads `ENABLED_CITIES` env var (default `"madrid"`), maps known city codes to provider instances, logs a warning for unknown codes
- [x] 5.4 Update `infrastructure/scheduler.py` to iterate over all registered providers and schedule one `IngestCityParkingData` job per provider; remove any hard-coded Madrid-specific instantiation
- [x] 5.5 Update `presentation/api/app.py` to instantiate the provider registry at startup and inject the Madrid provider (or all registered providers) into the scheduler

## 6. Tests

- [x] 6.1 Write unit tests for `MadridSerCallesProvider.get_records()` in `tests/unit/`: mock HTTP response, assert zone type extracted correctly from raw CSV `color` column (`"043000255 Azul"` → `zone_type = "Azul"`, `"081209246 Alta Rotación"` → `zone_type = "Alta Rotación"`), assert unrecognised zone type skips row, assert coordinates are not divided by 100, assert missing/empty `numero_plazas` yields `spot_count = -1` (row not skipped), assert rows missing mandatory CSV fields (`calle`, `color`, `gis_x`, `gis_y`) are skipped
- [x] 6.2 Write unit tests for `ZoneType` abstract class enforcement: subclass without `display_name` or `from_raw` raises `TypeError`; `MadridZoneType.from_raw()` returns correct member for known values and `None` for unknown
- [x] 6.3 Write unit tests for `SerZone` entity construction with `zone_type` and `spot_count`; assert `zone_code` and `zone_label` attributes no longer exist
- [x] 6.4 Update integration test for `SerZonePostgresRepository` to insert/retrieve records with `zone_type` and `spot_count`; assert old columns are gone
- [x] 6.5 Update e2e test for `GET /parking/ser-zone` to assert `zone_type` and `spot_count` appear in the response and `zone_label`/`zone_code` are absent
- [x] 6.6 Remove or update any tests that reference `CallejeroCsvParser`, `MADRID_CALLEJERO_URL`, `zone_code`, or `zone_label`
