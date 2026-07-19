## 1. Strict request schemas (reject unknown fields)

- [x] 1.1 Add `StrictRequestModel(BaseModel)` with `model_config = ConfigDict(extra="forbid")` to `presentation/api/schemas.py`
- [x] 1.2 Change every request-body model (`RegisterToyotaRequest`, `RegisterGenericRequest`, `PushLocationRequest`, `UpdateToyotaRequest`, `UpdateGenericRequest`, `SetVehicleSerParkingExemptionRequest`, `UpdateUserPreferencesRequest`, `ConnectElParkingRequest`, `UpdateNotificationPreferenceRequest`) to inherit from `StrictRequestModel` instead of `BaseModel`; leave response models on `BaseModel`
- [x] 1.3 Grep `frontend/src/api/*.ts` for each affected request body to confirm no legitimate extra fields are currently sent (would now 422)
- [x] 1.4 Add/adjust tests asserting an unrecognized field in a request body returns `422` for at least one representative endpoint (e.g. `POST /vehicles`)

## 2. VIN and Toyota-locale format validation

- [x] 2.1 Add a `field_validator` for `vin` on `RegisterToyotaRequest` enforcing `^[A-HJ-NPR-Z0-9]{17}$`, raising a `ValueError` (→ Pydantic `422`) on mismatch
- [x] 2.2 Add a `field_validator` for `locale` on `RegisterToyotaRequest` and `UpdateToyotaRequest` using `pytoyoda.utils.locale.is_valid_locale()`
- [x] 2.3 Add tests: malformed VIN rejected, well-formed VIN accepted; unknown locale rejected, known locale accepted

## 3. Defensive max_length bounds

- [x] 3.1 Add `Field(max_length=100)` to Toyota `username` and `locale` (register + update)
- [x] 3.2 Add `Field(max_length=200)` to Toyota `password` (register + update)
- [x] 3.3 Add `Field(max_length=100)` to `display_name` on `BaseRegisterVehicleRequest` and `BaseUpdateVehicleRequest`
- [x] 3.4 Add `Field(max_length=50)` to `city_code` on `SetVehicleSerParkingExemptionRequest`
- [x] 3.5 Add tests for at least one over-length field returning `422`

## 4. Path-parameter validation against known values

- [x] 4.1 Add a FastAPI dependency validating the `provider` path param on `DELETE /ser-ticket-providers/connections/{provider}` against the supported SER ticket provider set, returning `404` before invoking the disconnect use case
- [x] 4.2 Add a FastAPI dependency validating the `channel` path param on `DELETE /notifications/channels/{channel}` against `request.app.state.notification_channels.keys()`, returning `404` before invoking the remove-channel use case
- [x] 4.3 Add tests for both: unknown value → `404`, use case not invoked; known value → proceeds as before

## 5. Rate limiting for credential-bearing and auth endpoints

- [x] 5.1 Add `@limiter.limit("60/minute")` to `POST /vehicles` (`routers/vehicles.py`)
- [x] 5.2 Add `@limiter.limit("60/minute")` to `PUT /vehicles/{vehicle_id}` (`routers/vehicles.py`)
- [x] 5.3 Add `@limiter.limit("60/minute")` to `POST /ser-ticket-providers/connections` (`routers/ser_ticket_providers.py`)
- [x] 5.4 Add `@limiter.limit("60/minute")` to `GET /auth/google/callback` (`routers/auth.py`)
- [x] 5.5 Add a test confirming the 61st request within a minute to one of the newly-covered endpoints returns `429`

## 6. Shared vehicle-ownership dependency

- [x] 6.1 Add `require_owned_vehicle(vehicle_id: UUID, request: Request, current_user: User = Depends(get_current_user)) -> Vehicle` to `presentation/api/deps.py`: 404 if the vehicle doesn't exist, 403 if `vehicle.user_id != current_user.id`, else return it
- [x] 6.2 Replace each inline `vehicle = repo.find(...); if None: 404; if user_id mismatch: 403` block in `routers/vehicles.py` with `vehicle: Vehicle = Depends(require_owned_vehicle)`
- [x] 6.3 Confirm existing ownership-check tests still pass unchanged (behavior must be identical — 403/404 outcomes, not just refactored)

## 7. Reject unknown keys in notification config

- [x] 7.1 In `validate_notification_config()` (`domain/value_objects/notification_config_schema.py`), add a check: any key in `config` not present in `config_schema` raises `InvalidNotificationConfigError`
- [x] 7.2 Update the module docstring to remove the now-inaccurate "unknown/extra key in `config` itself is also ignored" note
- [x] 7.3 Add a test: `PUT /notifications/preferences/location_moved` with `config: {"threshold_m": 20, "unexpected_field": "value"}` returns `422` and leaves the existing row unchanged

## 8. Verification

- [x] 8.1 Run the full backend test suite (`./venv/bin/pytest tests/`) and confirm no regressions
- [ ] 8.2 Manually exercise the frontend against a running dev stack for vehicle register/update, SER parking exemption, ElParking connect, and notification preferences to confirm no legitimate flow now fails with `422` — SKIPPED: no live Docker stack available in this environment; static check of `frontend/src/api/*.ts` and the calling components (task 1.3) confirms request shapes match the new schemas exactly, but this has not been exercised against a running stack
- [x] 8.3 Update `openspec/specs/notification-type-preferences/spec.md` note: confirm delta spec matches implemented behavior before archive — verified: the delta spec's "Config with an unrecognized key is rejected" scenario matches `validate_notification_config()`'s new behavior; no drift found, no edits needed

## 9. Post-4R-review fixes

- [x] 9.1 In `deps.py`, extract `_fetch_owned_vehicle(vehicle_repo, vehicle_id, current_user) -> Vehicle` (the 404/403 check) as a private helper; have `require_owned_vehicle` call it; add `get_owned_vehicle_or_raise(request, vehicle_id, current_user) -> Vehicle` as a plain (non-`Depends`) function that also calls it — see design.md decision 5 amendment
- [x] 9.2 In `routers/vehicles.py`, change `update_vehicle` and `set_ser_parking_exemption` to take `current_user: User = Depends(get_current_user)` instead of `vehicle: Vehicle = Depends(require_owned_vehicle)`, and call `get_owned_vehicle_or_raise(request, vehicle_id, current_user)` as the first line of the handler body (after `body` is already a resolved parameter), restoring body-then-ownership ordering exactly as it was before this change
- [x] 9.3 Add a test: a non-owner sending a malformed body (e.g. an over-length `license_plate`) to the vehicle update endpoint gets `422`, not `403` — proving body validation still runs first for body-bearing routes
- [x] 9.4 In `limiter.py`, add `headers_enabled=True` to the `Limiter(...)` constructor so `429` responses carry a `Retry-After` header (applies to all six rate-limited endpoints, not just the newly-added ones)
- [x] 9.5 In `schemas.py`, add `Field(min_length=17, max_length=17)` to `RegisterToyotaRequest.vin`, consistent with its sibling fields in the same class
- [x] 9.6 In `schemas.py`, rename `_check_locale` to `_validate_locale` for naming consistency with `_validate_vin`
- [x] 9.7 Add a dedicated unit test in `test_deps.py` for `require_owned_vehicle` and `get_owned_vehicle_or_raise` (404 when vehicle missing, 403 when not owned, success when owned) — currently only covered indirectly via router tests
- [x] 9.8 Add a `429`-on-61st-request test for `update_vehicle` (mirroring the existing `register_vehicle` test) and for the Google OAuth callback
- [x] 9.9 Run `./venv/bin/pytest tests/` and confirm no regressions against the established baseline (696 passed / 103 pre-existing integration errors)

## 10. Re-review fixes (readability only)

A re-run 4R review on section 9's changes found 2 new WARNINGs (readability: undocumented `response: Response` params; resilience: `set_ser_parking_exemption` missing the non-owner+invalid-body regression test `update_vehicle` got) and 2 SUGGESTIONs (reliability: no test asserts `Retry-After` is present; readability: redundant `vin` length constraint undocumented). Per explicit maintainer decision, only the two readability findings are addressed here — the resilience WARNING and reliability SUGGESTION are deliberately left as-is (not important right now).

- [x] 10.1 Document why `response: Response` is required (not dead code) on `update_vehicle`/`register_vehicle` (`routers/vehicles.py`) and `get_ser_zone` (`routers/parking.py`), and add the same rationale as a comment on `headers_enabled=True` in `limiter.py`
- [x] 10.2 Document why `RegisterToyotaRequest.vin` has both a `Field(min_length=17, max_length=17)` bound and a regex validator enforcing the same length (`schemas.py`)
- [x] 10.3 Confirm lint/type-check/tests still pass after the comment-only changes
