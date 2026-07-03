## 1. Domain Layer

- [x] 1.1 Fill in `domain/value_objects/license_plate.py`: frozen dataclass with `value: str`, `MAX_LENGTH = 20`, `__post_init__` guard raising `ValueError` when exceeded
- [x] 1.2 Add `license_plate: str | None` field to `domain/entities/vehicle.py` `Vehicle` dataclass (after `vin`)
- [x] 1.3 Add `update_license_plate(vehicle_id: UUID, license_plate: str | None) -> None` abstract method to `domain/ports/vehicle_repository.py`

## 2. Infrastructure — ORM and Migration

- [x] 2.1 Add `Column("license_plate", String(20), nullable=True)` to `vehicles_table` in `infrastructure/orm/tables.py`
- [x] 2.2 Generate new Alembic migration `add_license_plate_to_vehicles` that adds the nullable `license_plate VARCHAR(20)` column to `vehicles` table; set `downgrade` to drop the column
- [x] 2.3 Update `PostgresVehicleRepository.save()` to include `license_plate=vehicle.license_plate` in the insert values
- [x] 2.4 Update `PostgresVehicleRepository._row_to_vehicle()` to map `license_plate=row.license_plate`
- [x] 2.5 Implement `update_license_plate(vehicle_id, license_plate)` in `PostgresVehicleRepository`: `UPDATE vehicles SET license_plate = :value WHERE id = :id`

## 3. Application Layer — Use Case

- [x] 3.1 Extend `UpdateVehicle.execute()` signature with `license_plate: str | None = _UNSET` sentinel; call `vehicle_repo.update_license_plate()` when a value other than `_UNSET` is received

## 4. Presentation Layer — Schemas, Factories, and Router

- [x] 4.1 Add `class BaseRegisterVehicleRequest(BaseModel)` to `presentation/api/schemas.py` with field `display_name: str`; make `RegisterToyotaRequest` and `RegisterGenericRequest` inherit from it (remove duplicated `display_name` from each)
- [x] 4.2 Add `class BaseUpdateVehicleRequest(BaseModel)` to `presentation/api/schemas.py` with fields `display_name: str` and `license_plate: str | None = Field(None, max_length=20)`; make `UpdateToyotaRequest` and `UpdateGenericRequest` inherit from it (remove duplicated `display_name` from each)
- [x] 4.3 Add `license_plate: str | None` to `VehicleListItem` schema
- [x] 4.4 Add `license_plate: str | None` to `VehicleDetailResponse` schema
- [x] 4.5 Add `license_plate: str | None` to `VehicleResponse` schema (registration response)
- [x] 4.6 Create `presentation/api/factories.py` with: `RegisterVehicleInput` dataclass (fields: `brand`, `display_name`, `vin`, `toyota_config`) and `VehicleRegisterFactory.build(body) -> RegisterVehicleInput` (encapsulates `ToyotaConfig` construction and `vin` fallback); `VehicleUpdateInput` dataclass (fields: `display_name`, `license_plate`, `username`, `locale`, `password`) and `VehicleUpdateFactory.build(body: BaseUpdateVehicleRequest) -> VehicleUpdateInput` (extracts brand-specific fields)
- [x] 4.7 Refactor `register_vehicle` router endpoint: import `VehicleRegisterFactory`, call `factory.build(body)`, pass result fields to `use_case.execute()`; include `license_plate=None` in `VehicleResponse`
- [x] 4.8 Refactor `update_vehicle` router endpoint: import `VehicleUpdateFactory`, call `factory.build(body)`, pass all fields (including `license_plate`) to `update_vehicle.execute()`
- [x] 4.9 Update `list_vehicles` handler: include `license_plate=item.vehicle.license_plate` in each `VehicleListItem`
- [x] 4.10 Update `_build_vehicle_detail` helper: include `license_plate=vehicle.license_plate` in `VehicleDetailResponse`

## 5. Frontend

- [x] 5.1 Add `license_plate: string | null` to `VehicleListItem` and `VehicleDetail` interfaces in `frontend/src/types/vehicle.ts`
- [x] 5.2 Add i18n keys in `frontend/public/locales/en/translation.json` and `es/translation.json`: `vehicle.licensePlate` (label), `vehicle.noLicensePlate` (placeholder)
- [x] 5.3 Update `VehicleCard.tsx`: display `license_plate` with label when set, localised placeholder when null
- [x] 5.4 Update `EditVehicleModal.tsx`: add optional `license_plate` text input field (pre-filled from current value) for all brands; include `license_plate` (empty string → `null`) in the PUT request body

## 6. Tests

- [x] 6.1 Unit test `LicensePlate` VO: valid construction, too-long value raises `ValueError` (`tests/domain/value_objects/test_license_plate.py`)
- [x] 6.2 Unit test `UpdateVehicle` use case: license plate is updated when provided, unchanged when sentinel is passed (`tests/application/use_cases/test_update_vehicle.py`)
- [x] 6.3 Unit test `VehicleRegisterFactory`: Toyota body builds a `ToyotaConfig` and sets `vin`; Generic body yields `toyota_config=None` and `vin=None` (`tests/presentation/test_factories.py`)
- [x] 6.4 Unit test `VehicleUpdateFactory`: Toyota body extracts username/locale/password, Generic body yields None for those fields; both include `license_plate` (`tests/presentation/test_factories.py`)
- [x] 6.5 Integration test `PostgresVehicleRepository.update_license_plate`: set a plate, verify row; clear to None, verify row (`tests/infrastructure/test_vehicle_repo_integration.py`)
- [x] 6.6 API test for `PUT /vehicles/{id}`: set plate returns 200 with plate in response; plate > 20 chars returns 422; clear plate returns 200 with null (`tests/presentation/test_vehicles_api.py`)
