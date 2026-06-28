## Context

The platform has stub scaffolding for vehicles (`Vehicle` entity, `VehicleProviderPort`, `ToyotaVehicleProvider`) but no implementation. The city parking layer already established the pattern to follow: a domain port, one or more infrastructure adapters, a registry reading an env var, and a scheduler driving periodic work. This change fills in the vehicle location layer using the same pattern, extended to support a second interaction mode (push).

The key constraints from the exploration session:
- Vehicle credentials are per-vehicle (not global env vars) to support future multi-vehicle and multi-user scenarios.
- Toyota credentials are sensitive; generic location token is not.
- Location history must be a full time-series, not last-known-only.
- Brand is a closed enum; new brands require code changes, not just config.

## Goals / Non-Goals

**Goals:**
- Provide a clean domain port for pull-based location providers.
- Implement Toyota adapter (pull via pytoyoda) and Generic adapter (push via HTTP endpoint).
- Store per-vehicle configuration securely: encrypt Toyota credentials, store generic token in cleartext.
- Persist full location history with source tagging (`pull` / `push`).
- Expose `POST /vehicles` (register), `GET /vehicles/{id}/location` (latest), and `POST /vehicles/{token}/location` (push ingest).
- Gate active brands via `ENABLED_BRANDS` env var (default: `generic`), mirroring city pattern.

**Non-Goals:**
- Multi-user support (owner/user_id on Vehicle is deferred to a future change).
- Vehicle autodiscovery from Toyota API.
- Location history query endpoint with date-range filtering (deferred).
- Encryption key rotation tooling.
- Non-GPS telemetry (fuel level, odometer, etc.).

## Decisions

### 1. Brand as a closed enum, not an open string

**Decision**: `Brand` is a `str`-based Python enum in `domain/value_objects/brand.py` with values `TOYOTA` and `GENERIC`. The `Vehicle` entity holds `brand: Brand`.

**Why**: Prevents invalid brand values at domain boundaries, makes exhaustive branching in the registry explicit (a new brand requires code changes, IDE tooling catches missing cases), and is queryable as a simple string in the DB.

**Alternative considered**: Open string with a registry dict. Rejected because it allows misspelled or unknown brands to silently enter the system without error.

---

### 2. One pull port, no push port

**Decision**: `VehiclePullLocationPort` is the only domain port for location. Push has no corresponding port — it is handled entirely by the presentation layer (HTTP endpoint) calling the `RecordVehicleLocation` use case directly.

**Why**: Push means the system *receives* data; there is nothing to abstract at the domain level. A `VehiclePushLocationPort` would have no meaningful contract — it would just be a pass-through with no behavior to vary across implementations.

**Alternative considered**: A unified `VehicleLocationPort` with a `mode` flag. Rejected because it forces push brands to stub out a `fetch_location` method that can never be called sensibly, polluting the interface.

---

### 3. Per-vehicle config table with selective encryption

**Decision**: A `vehicle_configs` table stores all brand-specific configuration. Toyota credentials (`username`, `password`, `locale`, `vin`) are serialised to JSON and encrypted with AES-128 (Fernet symmetric encryption, key from `ENCRYPTION_KEY` env var). The generic `location_token` is stored in cleartext in a dedicated indexed column.

**Why**: The generic token is an opaque random UUID. It cannot identify the user, does not authenticate any account, and must be queryable for O(1) endpoint dispatch. Encrypting it would require a hash index workaround (SHA-256 cleartext + encrypted blob) for no security gain. Toyota credentials are real account passwords and must be encrypted at rest.

**Alternative considered**: Encrypt all config uniformly (including the token). Rejected because it requires the SHA-256 hash trick, adds complexity, and provides no meaningful security benefit for the token.

**Alternative considered**: Separate tables per brand (`toyota_vehicle_configs`, `generic_vehicle_configs`). Rejected because the registry pattern already handles branching in code; a single table is simpler to migrate and query.

---

### 4. `RecordVehicleLocation` as the single write use case

**Decision**: Both the pull scheduler and the push HTTP endpoint call the same `RecordVehicleLocation` use case. The caller passes `source="pull"` or `source="push"`.

**Why**: There is no behavioural difference between storing a pull-derived location and a push-derived one. Sharing the use case avoids duplication and ensures consistent validation, timestamp handling, and persistence logic. The `source` tag is metadata for auditing/debugging, not a behaviour switch.

---

### 5. Brand registry mirrors city provider registry

**Decision**: `BrandRegistry` reads `ENABLED_BRANDS` (comma-separated, default `generic`), instantiates one `VehiclePullLocationPort` per pull-capable brand (currently only `toyota`). Generic is push-only and produces no entry in the pull registry. The scheduler receives the list of pull providers from the registry.

**Why**: Consistency with the existing `CityProviderRegistry` pattern reduces cognitive load. Operators enable/disable brands the same way they enable/disable cities.

**Note**: `ENABLED_BRANDS` controls which brands are accepted at vehicle registration. Generic is always accepted for push (its endpoint is always mounted), but registering a `generic` vehicle is only allowed when `generic` is in `ENABLED_BRANDS`.

---

### 6. Full location history, no pruning

**Decision**: Every `RecordVehicleLocation` call appends a new row to `vehicle_locations`. No overwrite, no pruning policy at this stage.

**Why**: History enables future features (zone dwell time, route reconstruction, parking detection). Storage cost is negligible at single-user scale (Toyota at 5-min intervals ≈ 288 rows/day per vehicle).

---

### 7. Fernet for symmetric encryption

**Decision**: Use `cryptography.fernet.Fernet` for encrypting Toyota credentials. The encryption key is a base64-encoded 32-byte key stored in `ENCRYPTION_KEY` env var.

**Why**: Fernet provides authenticated encryption (AES-128-CBC + HMAC-SHA256) — tampering with the ciphertext is detected. It is part of the `cryptography` library already commonly available in Python projects and requires no external key management service.

**Key generation**: `Fernet.generate_key()` — operators generate once and store in their secrets manager.

## Risks / Trade-offs

- **pytoyoda is unofficial** → Toyota may change their API without notice, breaking location fetch silently. Mitigation: log and record fetch errors per vehicle; scheduler continues for other vehicles on partial failure.
- **Single encryption key** → If `ENCRYPTION_KEY` leaks, all Toyota credentials are exposed. Mitigation: treat `ENCRYPTION_KEY` as a high-value secret (secrets manager, not .env in source). Key rotation is a future task.
- **No token expiry for generic** → A leaked `location_token` is permanently valid. Mitigation: expose a token regeneration endpoint in a future change. For now the token is per-vehicle and non-user-identifying.
- **No authentication on `POST /vehicles`** → Any caller can register a vehicle. Mitigation: the authentication change is tracked separately; this change does not add auth but does not break it either.

## Migration Plan

1. Add `cryptography` and `pytoyoda` to `requirements.txt`.
2. Add new Alembic migration: create `vehicles`, `vehicle_configs`, `vehicle_locations` tables.
3. Add `ENCRYPTION_KEY` and `ENABLED_BRANDS` to deployment env vars. `ENCRYPTION_KEY` is required when `toyota` is in `ENABLED_BRANDS`; the app raises `RuntimeError` at startup if missing.
4. Wire `VehicleLocationScheduler` into FastAPI lifespan alongside `ParkingIngestionScheduler`.
5. Mount new routers in `app.py`.

**Rollback**: Drop the three new tables (no existing data depends on them). Remove new routers and scheduler wiring. No existing functionality is affected.

## Open Questions

*(none — all design questions resolved during exploration)*
