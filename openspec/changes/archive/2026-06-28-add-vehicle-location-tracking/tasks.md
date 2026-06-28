## 1. Domain Value Objects and Entities

- [x] 1.1 Create `domain/value_objects/brand.py` — `Brand(str, Enum)` with `TOYOTA` and `GENERIC` values
- [x] 1.2 Implement `Vehicle` entity in `domain/entities/vehicle.py` — fields: `id: UUID`, `brand: Brand`, `display_name: str`, `vin: str | None`, `created_at: datetime`
- [x] 1.3 Implement `VehicleLocation` entity in `domain/entities/vehicle_location.py` — fields: `id: UUID`, `vehicle_id: UUID`, `latitude: float`, `longitude: float`, `recorded_at: datetime`, `received_at: datetime`, `source: Literal["pull", "push"]`
- [x] 1.4 Create `domain/value_objects/toyota_config.py` — frozen dataclass `ToyotaConfig(username, password, locale, vin)` (never persisted directly)
- [x] 1.5 Create `domain/value_objects/generic_config.py` — frozen dataclass `GenericConfig(location_token: str)`

## 2. Domain Ports

- [x] 2.1 Implement `VehiclePullLocationPort` in `domain/ports/vehicle_pull_location_port.py` — ABC with abstract method `fetch_location(vehicle_id: UUID, config: ToyotaConfig) -> VehicleLocation`
- [x] 2.2 Implement `VehicleRepository` port in `domain/ports/vehicle_repository.py` — `save`, `get_by_id`, `get_all_by_brand`
- [x] 2.3 Implement `VehicleConfigRepository` port in `domain/ports/vehicle_config_repository.py` — `save_toyota_config`, `save_generic_config`, `get_toyota_config`, `get_generic_config`, `find_vehicle_by_token`
- [x] 2.4 Implement `VehicleLocationRepository` port in `domain/ports/vehicle_location_repository.py` — `save`, `get_latest`
- [x] 2.5 Remove the empty `VehicleProviderPort` stub (replaced by `VehiclePullLocationPort`)

## 3. Domain Exceptions

- [x] 3.1 Add `VehicleNotFoundError`, `VehicleConfigNotFoundError`, `VehicleLocationNotFoundError`, `VinNotFoundInAccountError`, `BrandNotEnabledError` to `domain/exceptions.py`

## 4. Application Use Cases

- [x] 4.1 Implement `RegisterVehicle` use case in `application/use_cases/register_vehicle.py` — validates brand is enabled, creates `Vehicle`, generates token for generic, encrypts config for Toyota, saves both via repositories
- [x] 4.2 Implement `RecordVehicleLocation` use case in `application/use_cases/record_vehicle_location.py` — accepts `vehicle_id`, `lat`, `lon`, `recorded_at`, `source`; validates coords and timestamp; saves via `VehicleLocationRepository`
- [x] 4.3 Implement `GetLatestVehicleLocation` use case in `application/use_cases/get_latest_vehicle_location.py` — calls `VehicleLocationRepository.get_latest`, raises `VehicleLocationNotFoundError` if `None`

## 5. Configuration

- [x] 5.1 Add `get_enabled_brands() -> list[Brand]` to `config.py` — reads `ENABLED_BRANDS` (default `generic`), parses and validates against `Brand` enum
- [x] 5.2 Add `get_encryption_key() -> bytes` to `config.py` — reads `ENCRYPTION_KEY`, raises `RuntimeError` if missing when called; used only when Toyota is enabled
- [x] 5.3 Add `get_vehicle_poll_interval_minutes() -> int` to `config.py` — reads `VEHICLE_POLL_INTERVAL_MINUTES` (default `5`)

## 6. Encryption Helpers

- [x] 6.1 Add `cryptography` to `requirements.txt`
- [x] 6.2 Create `infrastructure/crypto.py` — `encrypt(data: dict, key: bytes) -> bytes` and `decrypt(ciphertext: bytes, key: bytes) -> dict` using `Fernet`

## 7. Database Schema Migration

- [x] 7.1 Create Alembic migration: `CREATE TABLE vehicles (id UUID PK, brand VARCHAR(20), display_name VARCHAR(255), vin VARCHAR(50) NULL, created_at TIMESTAMPTZ)`
- [x] 7.2 Create Alembic migration: `CREATE TABLE vehicle_configs (vehicle_id UUID PK FK, brand VARCHAR(20), encrypted_payload BYTEA NULL, location_token VARCHAR(64) NULL, updated_at TIMESTAMPTZ)` with index on `location_token WHERE NOT NULL`
- [x] 7.3 Create Alembic migration: `CREATE TABLE vehicle_locations (id UUID PK, vehicle_id UUID FK, latitude FLOAT8, longitude FLOAT8, recorded_at TIMESTAMPTZ, received_at TIMESTAMPTZ DEFAULT NOW(), source VARCHAR(10))` with composite index on `(vehicle_id, recorded_at DESC)`

## 8. ORM Tables

- [x] 8.1 Add `VehicleTable`, `VehicleConfigTable`, `VehicleLocationTable` SQLAlchemy `Table` definitions to `infrastructure/orm/tables.py`

## 9. Infrastructure Repositories

- [x] 9.1 Implement `PostgresVehicleRepository` in `infrastructure/repositories/postgres/vehicle_repo.py`
- [x] 9.2 Implement `PostgresVehicleConfigRepository` in `infrastructure/repositories/postgres/vehicle_config_repo.py` — encrypts/decrypts Toyota payload via `crypto.py`; stores generic token as cleartext
- [x] 9.3 Implement `PostgresVehicleLocationRepository` in `infrastructure/repositories/postgres/vehicle_location_repo.py`

## 10. Toyota Location Provider

- [x] 10.1 Add `pytoyoda` to `requirements.txt`
- [x] 10.2 Implement `ToyotaLocationProvider` in `infrastructure/vehicle_providers/toyota/location_provider.py` — implements `VehiclePullLocationPort`; authenticates via pytoyoda, filters by VIN, returns `VehicleLocation` with `source="pull"`
- [x] 10.3 Remove empty `ToyotaVehicleProvider` stub (replaced by `ToyotaLocationProvider`)

## 11. Brand Registry

- [x] 11.1 Create `infrastructure/vehicle_providers/brand_registry.py` — reads `ENABLED_BRANDS`, returns list of `VehiclePullLocationPort` instances for pull-capable brands; logs warning for unknown brands; validates `ENCRYPTION_KEY` present when toyota is enabled

## 12. Vehicle Location Scheduler

- [x] 12.1 Create `infrastructure/vehicle_location_scheduler.py` — mirrors `ParkingIngestionScheduler`; on each tick: fetches all Toyota vehicles, decrypts configs, calls `ToyotaLocationProvider.fetch_location`, calls `RecordVehicleLocation`; logs and continues on per-vehicle errors

## 13. Presentation — API Schemas

- [x] 13.1 Add request/response Pydantic schemas to `presentation/api/schemas.py`: `RegisterVehicleRequest` (union discriminated by brand), `VehicleResponse`, `PushLocationRequest`, `VehicleLocationResponse`

## 14. Presentation — Routers

- [x] 14.1 Create `presentation/api/routers/vehicles.py` with:
  - `POST /vehicles` → `RegisterVehicle` use case
  - `GET /vehicles/{vehicle_id}/location` → `GetLatestVehicleLocation` use case
  - `POST /vehicles/{token}/location` → token lookup + `RecordVehicleLocation` use case; rate-limited

## 15. Application Wiring

- [x] 15.1 Wire `VehicleLocationScheduler` into FastAPI lifespan in `presentation/api/app.py` (start/stop alongside `ParkingIngestionScheduler`)
- [x] 15.2 Mount `vehicles_router` in `app.py`
- [x] 15.3 Allow `POST` method in CORS middleware (currently only `GET` is allowed)

## 16. Tests

- [x] 16.1 Unit tests for `Brand` enum — valid values, invalid string rejection
- [x] 16.2 Unit tests for `RecordVehicleLocation` — valid coords, future timestamp rejection, source tagging
- [x] 16.3 Unit tests for `RegisterVehicle` — toyota and generic paths, disabled brand rejection
- [x] 16.4 Unit tests for `GetLatestVehicleLocation` — found and not-found cases
- [x] 16.5 Unit tests for `crypto.py` — encrypt/decrypt round-trip
- [x] 16.6 Unit tests for `BrandRegistry` — enabled brands, unknown brand warning, empty list for generic-only
- [x] 16.7 Integration tests for `PostgresVehicleConfigRepository` — Toyota payload encrypted in DB, generic token stored cleartext
- [x] 16.8 Integration tests for `PostgresVehicleLocationRepository` — `get_latest` returns row with highest `recorded_at`
- [x] 16.9 API tests for `POST /vehicles` — Toyota and generic registration, disabled brand 422
- [x] 16.10 API tests for `POST /vehicles/{token}/location` — valid push, unknown token 404, invalid coords 422, future timestamp 422
- [x] 16.11 API tests for `GET /vehicles/{id}/location` — found, no history 404, unknown vehicle 404
