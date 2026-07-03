## Context

The `Vehicle` domain entity has `vin: str | None` (Toyota-only) but no `license_plate` field. A `LicensePlate` VO stub exists at `domain/value_objects/license_plate.py` but is empty. License plates are needed downstream for automated SER ticket creation. The plate is brand-agnostic, nullable, and only settable via update (not at registration).

Currently, update request schemas (`UpdateToyotaRequest`, `UpdateGenericRequest`) are defined independently in `presentation/api/schemas.py`. Brand-specific object construction (e.g. extracting `password`, `username`, `locale`) is done inline in the vehicles router with `isinstance` checks.

## Goals / Non-Goals

**Goals:**
- Add `license_plate: str | None` (max 20 chars) to `Vehicle` entity, ORM table, and all read/write API surfaces.
- Introduce `BaseUpdateVehicleRequest` so all current and future brand update schemas inherit `display_name` and `license_plate` without repetition.
- Replace scattered `isinstance` brand dispatch in the router with a `VehicleUpdateFactory` that builds the use-case input from any `BaseUpdateVehicleRequest`.
- Fill the empty `LicensePlate` VO stub as a thin validated wrapper.
- Update the frontend to display and edit the plate field.

**Non-Goals:**
- Format/regex validation of the plate string (Spain has multiple formats; clients enforce nothing beyond max length).
- Exposing license plate on the registration endpoint (`POST /vehicles`).
- Encrypting or masking the plate (it is not a credential).

## Decisions

### D1 — `LicensePlate` VO as a thin str wrapper, not a plain str
**Decision**: Fill the stub as `@dataclass(frozen=True) class LicensePlate` wrapping a `value: str` with a `MAX_LENGTH = 20` class constant and a `__post_init__` length guard.
**Rationale**: Keeps the domain model explicit and makes the constraint discoverable without adding a regex lock-in. The VO is created once at the use-case boundary; everywhere else it travels as its `.value` string.
**Alternative considered**: Just use `str` everywhere. Rejected because the existing stub signals intent to have a typed VO, and a thin wrapper costs almost nothing.

### D2 — `BaseUpdateVehicleRequest` in the presentation schemas layer
**Decision**: Add `class BaseUpdateVehicleRequest(BaseModel)` with `display_name: str` and `license_plate: str | None = Field(None, max_length=20)`. `UpdateToyotaRequest` and `UpdateGenericRequest` inherit from it (adding their own `brand` discriminator and extra fields).
**Rationale**: All brands share the same two base fields; inheritance avoids repetition and ensures future brands get `license_plate` automatically.
**Alternative considered**: Keep the two request classes independent, duplicate the field. Rejected — violates DRY and the user explicitly requested this pattern.

### D3 — `VehicleUpdateFactory` in the presentation layer
**Decision**: Add `presentation/api/factories.py` with a `VehicleUpdateFactory.build(body: BaseUpdateVehicleRequest) -> VehicleUpdateInput` dataclass. The router imports the factory from the same presentation layer and passes the result to `UpdateVehicle.execute()`.
**Rationale**: The factory translates a Pydantic request schema (a presentation-layer type) into use-case parameters — that is an adapter concern, not an application concern. Placing it in `application/` would create an outward dependency (application → presentation), violating the Clean Architecture dependency rule. Keeping it in `presentation/api/` maintains the correct inward flow: Presentation → Application → Domain.
**Alternative considered**: Place in `application/factories/`. Rejected — the application layer must not import from the presentation layer.
**Alternative considered**: Keep `isinstance` inline in the router. Rejected — the factory pattern was explicitly requested and improves readability and testability.

### D4 — `BaseRegisterVehicleRequest` base class and `VehicleRegisterFactory` in the presentation layer
**Decision**: Add `class BaseRegisterVehicleRequest(BaseModel)` with `display_name: str`. `RegisterToyotaRequest` and `RegisterGenericRequest` inherit from it (keeping their own `brand: Literal[...]` discriminator and brand-specific fields). Add `VehicleRegisterFactory` to `presentation/api/factories.py` alongside `VehicleUpdateFactory`: `build(body) -> RegisterVehicleInput` dataclass (fields: `brand`, `display_name`, `vin`, `toyota_config`) encapsulating the `ToyotaConfig` construction and `getattr(body, "vin", None)` fallback.
**Rationale**: Mirrors the update pattern exactly: common fields on a base class, brand dispatch in a presentation-layer factory, router stays thin and free of `isinstance` chains. Consistent pattern across all vehicle write endpoints.
**Alternative considered**: Leave registration as-is (only apply the pattern to update). Rejected — inconsistency between endpoints would be confusing; applying the pattern uniformly costs one extra dataclass and is cleaner long-term.

### D5 — `license_plate` column on `vehicles_table` (nullable VARCHAR 20)
**Decision**: Add `Column("license_plate", String(20), nullable=True)` to `vehicles_table` and a dedicated Alembic migration.
**Rationale**: The plate is a property of the vehicle (not brand config), so it belongs on `vehicles_table` alongside `display_name` and `vin`. Nullable means no default needed; existing rows get `NULL`.
**Alternative considered**: Store on `vehicle_configs_table`. Rejected — it is brand-agnostic and belongs on the core vehicle row.

### D6 — `UpdateVehicle` use case receives `license_plate` as an optional param
**Decision**: Extend `UpdateVehicle.execute()` with `license_plate: str | None = None` and call a new `vehicle_repo.update_license_plate()` method when the value is not the sentinel "not provided".
**Rationale**: Use case stays thin; repo handles the SQL. A `None` value means "set plate to null"; we need a separate sentinel (`UNSET = object()`) to distinguish "caller wants to clear the plate" from "caller did not mention the plate".

## Risks / Trade-offs

- **Sentinel vs. None ambiguity** → Use a module-level `_UNSET` sentinel in the use case so `None` can mean "clear the plate" if needed. For now the PUT body sends `null` to clear, so this is exercised from day one.
- **Migration on live DB** → `ALTER TABLE vehicles ADD COLUMN license_plate VARCHAR(20) NULL` is non-blocking on PostgreSQL (no table rewrite for nullable columns). No rollback complexity.
- **Frontend i18n** → New strings ("License plate", "Sin matrícula") must be added to both `en.json` and `es.json` translation files.

## Migration Plan

1. Run Alembic migration (adds `license_plate` column as NULL, no data backfill needed).
2. Deploy backend (new field appears in all responses as `null` for existing vehicles).
3. Deploy frontend (shows plate field in card and edit modal; blank for existing vehicles).
4. Rollback: drop the column migration; revert backend + frontend. No data loss risk since field is new.
