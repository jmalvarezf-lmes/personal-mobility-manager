## Why

The backend API is exposed to real users but its request validation is inconsistent: unknown JSON fields are silently dropped instead of rejected, several fields (VIN, Toyota credentials, city codes, path-param identifiers) have no format or length bounds, `slowapi` rate limiting is wired globally but applied to only 2 of ~30 endpoints (none of them credential-bearing), and per-vehicle ownership checks are duplicated ad hoc across routers instead of enforced through one shared mechanism. Hardening this now, while the endpoint surface is still small, is cheaper than retrofitting it later.

## What Changes

- Reject unknown top-level fields on every request body schema (`extra="forbid"` via Pydantic v2 `model_config`), instead of the current default of silently discarding them.
- Add format/bounds validation to previously unconstrained fields:
  - `vin`: ISO 3779 shape (`^[A-HJ-NPR-Z0-9]{17}$`)
  - Toyota `locale`: validated via `pytoyoda.utils.locale.is_valid_locale()`
  - `username`, `password` (Toyota), `display_name`, `city_code`: defensive `max_length` bounds (no stricter format exists for these)
- Constrain string path params (`provider` on `DELETE /ser-ticket-providers/connections/{provider}`, `channel` on `DELETE /notifications/channels/{channel}`) to their known value sets instead of passing arbitrary strings straight through to the use case layer. (`type_key` on the notification-preferences routes is already validated against the catalog with a 404 — no change needed there.)
- Extend `@limiter.limit(...)` rate limiting to credential-bearing and auth endpoints: Toyota vehicle register/update, ElParking connect, and the Google OAuth callback.
- **BREAKING**: `PUT /notifications/preferences/{type_key}` now rejects a `config` object containing any key not declared in that notification type's `config_schema`, reversing the current documented "ignore extra keys" behavior (`notification_config_schema.py`).
- Consolidate the repeated `vehicle.user_id != current_user.id` ownership check (currently copy-pasted across 5+ routes in `routers/vehicles.py`) into one shared FastAPI dependency, with no change to the resulting 403 behavior.

## Capabilities

### New Capabilities
- `api-request-validation`: Baseline request-validation policy for the FastAPI layer — reject unknown request fields by default, and the specific format/bounds rules applied to previously-unconstrained fields and path params.
- `api-rate-limiting`: Which endpoint classes require rate limiting (credential-bearing and auth endpoints) and the limits applied.

### Modified Capabilities
- `notification-type-preferences`: The "Authenticated user can update a single notification type's preference" requirement changes — `config` conformance to `config_schema` now also means "no keys beyond what `config_schema` declares," where previously extra keys were silently ignored.

## Impact

- **Code**: `presentation/api/schemas.py` (all request models), `presentation/api/routers/*.py` (path-param typing, new rate-limit decorators), `domain/value_objects/notification_config_schema.py` (reject-unknown-keys logic), a new shared ownership-check dependency in `presentation/api/deps.py`.
- **API contract**: Existing clients (the project's own frontend) that send extra/unrecognized fields, or extra keys inside notification `config`, will now get `422` instead of having those fields silently ignored. No currently-legitimate request shape changes.
- **Dependencies**: No new dependencies — `pydantic`, `slowapi`, and `pytoyoda` (for locale validation) are already present.
