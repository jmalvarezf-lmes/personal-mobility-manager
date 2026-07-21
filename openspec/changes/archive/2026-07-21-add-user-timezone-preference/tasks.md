## 1. Backend: schema and persistence

- [x] 1.1 Add Alembic migration adding nullable `timezone TEXT` column to `user_preferences` (follow `m0n1o2p3q4r5_add_notification_language_to_user_preferences.py` as the template)
- [x] 1.2 Add `timezone` column to the `user_preferences` table definition in the ORM/table layer
- [x] 1.3 Add `timezone: str | None` field to the `UserPreferences` domain entity (`src/mobility_manager/domain/entities/user_preferences.py`)
- [x] 1.4 Update `UserPreferencesRepository` port and Postgres implementation: `update(...)` accepts and persists `timezone`; row-mapping includes it (`src/mobility_manager/domain/ports/user_preferences_repository.py`, `src/mobility_manager/infrastructure/repositories/postgres/user_preferences_repo.py`)

## 2. Backend: API

- [x] 2.1 Add `timezone` to `UserPreferencesResponse` and `UpdateUserPreferencesRequest` schemas (`src/mobility_manager/presentation/api/schemas.py`)
- [x] 2.2 In `routers/preferences.py`, validate non-null `timezone` against `zoneinfo.available_timezones()`, rejecting unrecognized values with `422` (mirror the existing `SUPPORTED_LANGUAGES` check); `null` always accepted
- [x] 2.3 Wire `timezone` through `GET /preferences` and `PUT /preferences` handlers

## 3. Backend: tests

- [x] 3.1 Extend `tests/infrastructure/test_user_preferences_repo_integration.py` to cover `timezone` persistence and clearing
- [x] 3.2 Extend `tests/presentation/test_preferences_api.py` with cases: valid timezone accepted, unrecognized timezone rejected (422), null clears the preference, GET reflects saved value

## 4. Frontend: timezone resolution + formatting utility

- [x] 4.1 Add a small formatting utility (new file, e.g. `frontend/src/utils/timezone.ts`) implementing the resolution cascade: saved preference → `Intl.DateTimeFormat().resolvedOptions().timeZone` → `'UTC'`, plus a `formatInTimezone(isoString, zone)` helper using `Intl.DateTimeFormat(locale, { timeZone, timeZoneName: 'short', ... })` that returns the formatted time suffixed with the zone's abbreviation for that specific instant's date (e.g. "14:32 CEST")
- [x] 4.2 Add a helper that lists all IANA zones via `Intl.supportedValuesOf('timeZone')` with a guarded fallback (small hardcoded list, or empty list) if unsupported, and computes each zone's *current* abbreviation (evaluated against today's date, for the picker label only) via the same `Intl.DateTimeFormat` mechanism as 4.1

## 5. Frontend: preferences page

- [x] 5.1 Add `timezone` to the `UserPreferences` TS interface and to request/response handling in `frontend/src/api/preferences.ts`
- [x] 5.2 Add a searchable timezone picker control to `PreferencesPage.tsx` (filter-as-you-type over the zone list from 4.2, each option labeled `"<Zone> (<abbreviation>)"`), including a way to clear the selection back to unset
- [x] 5.3 Wire the control to save via `PUT /preferences` and reflect the persisted value on load/success

## 6. Frontend: apply to location history modal

- [x] 6.1 In `VehicleLocationHistoryModal.tsx`, replace the raw `recorded_at` rendering in list rows with `formatInTimezone` using the resolved display timezone (includes the per-row abbreviation, e.g. "14:32 CEST")
- [x] 6.2 Do the same for the `recorded_at` shown in map pin popups
- [x] 6.3 Confirm chronological ordering/polyline logic still sorts on the raw UTC values, not the formatted display string (no behavior change expected, verify only)

## 7. Frontend: tests

- [x] 7.1 Add/extend `frontend/e2e/preferences.spec.ts` covering: selecting a timezone by search, saving, reload reflects it, clearing it
- [x] 7.2 Add a unit test for the resolution cascade utility (preference set / preference null with mocked `Intl` / both unavailable → UTC) — implemented as `frontend/e2e/timezone-utils.spec.ts`, run via Playwright's Node-side test runner (no `page`/browser involved) since the project has no vitest/jest; see apply-phase report for rationale
- [x] 7.3 Add/extend a test for `VehicleLocationHistoryModal` asserting displayed timestamps reflect the resolved timezone rather than raw UTC, and include the zone abbreviation — `frontend/e2e/vehicle-location-history-modal.spec.ts`
- [x] 7.4 Add a unit test asserting the same `Europe/Madrid`-preference entries recorded in January vs. July show "CET" and "CEST" respectively — covered in both `timezone-utils.spec.ts` (pure function) and `vehicle-location-history-modal.spec.ts` (rendered modal)
