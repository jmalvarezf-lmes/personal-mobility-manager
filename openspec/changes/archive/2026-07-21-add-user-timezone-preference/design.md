## Context

`VehicleLocationHistoryModal` (added in #45) renders `recorded_at` as a raw UTC ISO string — there is no date-formatting layer anywhere in the frontend today, and no timezone/date library in either `frontend/package.json` or `pyproject.toml`. Separately, `user_preferences` already holds per-user scalar settings (`notification_language`, `preferred_notification_channel`, ...) added incrementally via simple Alembic `add_column` migrations, validated in `routers/preferences.py`, and edited on `PreferencesPage.tsx`. This change adds `timezone` as one more such field, and adds the first client-side date-formatting logic to render it.

## Goals / Non-Goals

**Goals:**
- Let a user optionally pick an IANA timezone that persists across sessions/devices.
- When unset, fall back to the browser's detected timezone; when that's unavailable, fall back to UTC.
- Apply this only to the timestamps a user actually reads in the location history modal (list rows + map pin popups).
- Reuse the existing `user_preferences` add-a-field pattern exactly — no new table, no new architectural layer.

**Non-Goals:**
- No backend timestamp formatting or locale-aware rendering (API keeps returning UTC ISO8601, unchanged).
- No change to `received_at`, ordering, pagination cursors, or any other internal/non-displayed datetime — those remain UTC end-to-end.
- No auto-persisting of a "detected" default back to the server. The column stays `NULL` until the user explicitly saves a choice.
- No new npm/pip dependency — timezone enumeration and formatting use the native `Intl` API (frontend) and stdlib `zoneinfo` (backend validation only).

## Decisions

**1. Conversion happens entirely client-side; the API is untouched.**
`GET /vehicles/{id}/locations` keeps returning raw UTC ISO strings. The frontend resolves a display timezone and formats at render time. This avoids coupling the location API's response shape to user preferences, and keeps the backend free of locale/formatting concerns — consistent with `Non-Goals`.

**2. Resolution cascade, computed at render time, nothing written as a side effect:**
```
displayZone = userPreference ?? Intl.DateTimeFormat().resolvedOptions().timeZone ?? 'UTC'
```
No "detect once and persist" step. Rationale: a user who cares about a stable/specific zone can always save one explicitly; for everyone else, following the browser live is simpler to implement and reason about, and avoids a special-cased first-visit write-back. This was chosen over persisting a detected default specifically to avoid extra mechanism for a case the user can already resolve by setting a preference.

**3. Timezone picker lists the full IANA set via `Intl.supportedValuesOf('timeZone')` (frontend-only, no dependency), not a curated subset.**
Labeled per entry as `<Zone> (<current abbreviation>)`, e.g. `Europe/Madrid (CEST)`, computed via `Intl.DateTimeFormat(locale, { timeZone, timeZoneName: 'short' })` evaluated against *today's* date — this is a label for zone selection, not a stored value, so using "now" for the abbreviation shown in the picker is acceptable even though the same zone's abbreviation shifts across DST boundaries.

**4. Per-row abbreviations, shown next to each history entry, are computed per that row's own `recorded_at` date, not the picker's "now".**
`Europe/Madrid` is `CET` in January and `CEST` in July for the same IANA zone — the abbreviation is a function of (zone, instant), not zone alone. `Intl.DateTimeFormat` handles this correctly per-call with no extra logic needed; this is called out only so the two call sites (static picker list vs. per-row formatting) aren't conflated into one cached label.

**5. Backend validates `timezone` against `zoneinfo.available_timezones()`, mirroring the `SUPPORTED_LANGUAGES` check already used for `notification_language` in `routers/preferences.py`.**
`null` is always accepted (clears the preference); any non-null value must be a recognized IANA key or the request is rejected with `422`, same contract shape as the existing `notification_language` validation.

**6. `timezone` is added to `user_preferences` as one more nullable column via a plain Alembic `add_column` migration**, following the exact precedent of `notification_language`'s migration — entity, table, repo `update`, `GET`/`PUT /preferences` schema, and `PreferencesPage.tsx` control all gain one more field each, no new table or endpoint.

## Risks / Trade-offs

- **[Risk] A user with `timezone = NULL` sees timestamps shift if their device's OS/browser timezone changes (e.g. travel).** → Mitigation: this is accepted behavior per Decision 2 — the user can pin a specific zone at any time via the preferences page if stability matters more than following their device.
- **[Risk] `Intl.supportedValuesOf` is a relatively recent API (browser support landed a few years back); very old browsers may lack it.** → Mitigation: guard with a feature check and fall back to a small hardcoded zone list (or hide the picker gracefully) if unsupported — resolution cascade already falls back to UTC regardless, so the worst case is degraded picker UX, not incorrect timestamps.
- **[Trade-off] Two different call sites compute timezone abbreviations at two different instants (picker: "now"; history rows: each row's own date).** → Acceptable per Decision 4; documented here so a future reader doesn't try to unify them into a single cached abbreviation.

## Migration Plan

1. Alembic migration: add nullable `timezone TEXT` column to `user_preferences`.
2. Backend: entity, repo `update`, `GET`/`PUT /preferences` schema + validation (mirrors `notification_language`).
3. Frontend: extend `UserPreferences` TS interface + `PreferencesPage.tsx` with the timezone picker.
4. Frontend: add the resolution cascade + `Intl`-based formatting utility, apply it to `VehicleLocationHistoryModal.tsx`'s list rows and map popups.

No rollback complexity: the column is nullable and additive; reverting the migration is a plain column drop with no data-loss implications beyond the preference itself.

## Open Questions

None outstanding. The history modal displays the resolved zone's abbreviation next to each timestamp (e.g. "14:32 CEST"), computed per-row via `Intl.DateTimeFormat(locale, { timeZone, timeZoneName: 'short' })` against that row's own `recorded_at` date — see Decision 4.
