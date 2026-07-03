## Why

Vehicles in the system lack a license plate field, which is needed for automating SER parking ticket creation (the plate must be provided to the parking service). The plate is optional at registration time but must be settable afterwards via the existing update flow.

## What Changes

- Add `license_plate: str | None` (max 20 chars, no format validation) to the `Vehicle` domain entity and `vehicles_table`.
- Expose `license_plate` on all vehicle read responses (`GET /vehicles`, `GET /vehicles/{id}`).
- Allow `license_plate` to be set via `PUT /vehicles/{id}` for all brands.
- Introduce a `BaseRegisterVehicleRequest` Pydantic base class carrying `display_name`; `RegisterToyotaRequest` and `RegisterGenericRequest` inherit from it — future brand types share the common field automatically.
- Introduce a `BaseUpdateVehicleRequest` Pydantic base class carrying `display_name` and `license_plate`; `UpdateToyotaRequest` and `UpdateGenericRequest` inherit from it — future brand types get the field automatically.
- Introduce presentation-layer factories (`VehicleRegisterFactory`, `VehicleUpdateFactory`) in `presentation/api/factories.py` to centralise brand-specific dispatch for both registration and update, replacing `isinstance` chains in the router.
- Fill in (or thin-wrap) the existing empty `LicensePlate` VO stub.
- Add a new Alembic migration for the nullable `license_plate` column.
- Update the frontend vehicle card and edit modal to display and edit the plate.

## Capabilities

### New Capabilities

- `vehicle-license-plate`: Ability to store and update an optional license plate on a vehicle, and surface it in all vehicle read responses.

### Modified Capabilities

- `vehicle-update`: `PUT /vehicles/{id}` now accepts `license_plate` (optional, max 20 chars) for all brands via the new base request class.
- `vehicle-list`: `GET /vehicles` response objects now include `license_plate: str | null`.
- `vehicle-detail`: `GET /vehicles/{id}` response now includes `license_plate: str | null`.
- `vehicle-management-ui`: Vehicle card and edit modal show and allow editing of the license plate field.

## Impact

- **Backend**: `domain/entities/vehicle.py`, `domain/value_objects/license_plate.py`, `infrastructure/orm/tables.py`, `infrastructure/repositories/postgres/vehicle_repo.py`, `application/use_cases/update_vehicle.py`, `presentation/api/schemas.py`, `presentation/api/factories.py` (new), `presentation/api/routers/vehicles.py`
- **Database**: New Alembic migration — `ALTER TABLE vehicles ADD COLUMN license_plate VARCHAR(20) NULL`
- **Frontend**: `frontend/src/types/vehicle.ts`, `frontend/src/components/VehicleCard.tsx`, `frontend/src/components/EditVehicleModal.tsx`, `frontend/src/api/vehicles.ts`
- **No breaking changes**: `license_plate` is nullable everywhere; existing clients receive `null` for vehicles without a plate.
