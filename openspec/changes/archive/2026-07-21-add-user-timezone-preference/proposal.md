## Why

Vehicle location history currently renders raw UTC ISO timestamps verbatim (`recorded_at` in `VehicleLocationHistoryModal`), forcing users to mentally convert to their local time. Users should be able to view these timestamps in a timezone of their choosing, defaulting to their browser's detected timezone.

## What Changes

- Add a nullable `timezone` field to `user_preferences` (IANA zone identifier, e.g. `Europe/Madrid`), following the same pattern as `notification_language`.
- Expose `timezone` on `GET /preferences` and `PUT /preferences`, validated against the set of IANA zone names recognized by the backend.
- Add a searchable timezone picker to the Preferences page, listing IANA zones with a city-style label and their current UTC offset/abbreviation (e.g. "Europe/Madrid (CEST)"), plus an option to clear the preference.
- Format the `recorded_at` timestamps shown in `VehicleLocationHistoryModal` (list rows and map pin popups) using the resolved timezone: the user's saved preference if set, otherwise the browser's detected timezone, otherwise UTC. This resolution and formatting happens entirely client-side.
- Timestamps used for internal purposes (ordering, pagination cursors, `received_at`, any other non-user-facing datetime) are unaffected and remain UTC end-to-end — only the two *displayed* `recorded_at` values in the history modal are reformatted.

## Capabilities

### New Capabilities
(none — this extends two existing capabilities)

### Modified Capabilities
- `user-preferences`: adds a `timezone` field (entity, table column, repository `update`, `GET`/`PUT /preferences` schema and validation, Preferences page control).
- `vehicle-location-history-ui`: the modal's displayed `recorded_at` values (list rows and map popups) are rendered in the resolved timezone instead of raw UTC.

## Impact

- **Backend**: `user_preferences` table migration; `UserPreferences` entity; `UserPreferencesRepository`; `presentation/api/schemas.py` and `routers/preferences.py` (validation against IANA zone names, e.g. Python's `zoneinfo.available_timezones()`).
- **Frontend**: `frontend/src/api/preferences.ts` (`timezone` field); `PreferencesPage.tsx` (new picker control); `VehicleLocationHistoryModal.tsx` (introduces the app's first client-side date-formatting logic, using the native `Intl` API — no new dependency).
- No changes to API response shapes for location data, no changes to ordering/pagination logic, no backend timestamp formatting.
