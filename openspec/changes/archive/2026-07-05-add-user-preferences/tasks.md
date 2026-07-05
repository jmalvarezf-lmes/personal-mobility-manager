## 1. Domain layer

- [x] 1.1 `domain/entities/user_preferences.py` — frozen dataclass `UserPreferences` with `user_id: UUID`, `default_ticket_duration_minutes: int`, `auto_create_ticket: bool`, `updated_at: datetime`
- [x] 1.2 `domain/ports/user_preferences_repository.py` — abstract `UserPreferencesRepository` with `ensure_default(user_id: UUID) -> None`, `find_by_user_id(user_id: UUID) -> UserPreferences | None`, `update(user_id: UUID, default_ticket_duration_minutes: int, auto_create_ticket: bool) -> UserPreferences`

## 2. Database migration

- [x] 2.1 Add Alembic migration creating `user_preferences` table: `user_id UUID PRIMARY KEY REFERENCES users(id)`, `default_ticket_duration_minutes INT NOT NULL DEFAULT 60`, `auto_create_ticket BOOLEAN NOT NULL DEFAULT false`, `updated_at TIMESTAMP WITH TIME ZONE NOT NULL`
- [x] 2.2 Add `user_preferences_table` to `infrastructure/orm/tables.py`, following the existing `Table(...)` style used for `vehicle_configs_table`

## 3. Infrastructure layer

- [x] 3.1 `infrastructure/repositories/postgres/user_preferences_repo.py` — `PostgresUserPreferencesRepository` implementing the port using SQLAlchemy Core:
  - `ensure_default`: `INSERT ... ON CONFLICT (user_id) DO NOTHING` with default values
  - `find_by_user_id`: `SELECT` by `user_id`, return `None` if no row
  - `update`: `UPDATE ... WHERE user_id = :user_id`, refreshing `updated_at`, returning the persisted row
- [x] 3.2 Wire `PostgresUserPreferencesRepository` into `app.py` (instantiate, store on `app.state`), mirroring how `user_repo` and `vehicle_config_repo` are wired

## 4. Login integration (user-identity delta)

- [x] 4.1 Update `authenticate_google_user.py` use case to call `user_preferences_repo.ensure_default(user.id)` right after the `users` upsert succeeds, within the same use case invocation
- [x] 4.2 Resolved: `users` upsert and `ensure_default` remain two independently atomic, idempotent operations (not a shared transaction) — confirmed safe to sequence since `ensure_default` is `ON CONFLICT DO NOTHING` and self-heals on next login if interrupted. `design.md` and specs updated to describe this accurately.
- [x] 4.3 Update/extend `tests/application/use_cases/test_authenticate_google_user.py` to assert `ensure_default` is called with the upserted user's id

## 5. API layer

- [x] 5.1 Add `UserPreferencesResponse` and `UpdateUserPreferencesRequest` (with `default_ticket_duration_minutes: int` validated `gt=0`, `auto_create_ticket: bool`) to `presentation/api/schemas.py`
- [x] 5.2 `presentation/api/routers/preferences.py` — new router with:
  - `GET /preferences` — `Depends(get_current_user)`, returns current user's preferences via `find_by_user_id` (should always exist post-login; treat missing as a 500/assertion, not a 404, since login guarantees the row)
  - `PUT /preferences` — `Depends(get_current_user)`, validates request, calls `update`, returns the updated preferences
- [x] 5.3 Register `preferences_router` in `app.py` (`app.include_router(preferences_router)`)

## 6. Backend tests

- [x] 6.1 `tests/infrastructure/test_user_preferences_repo_integration.py` — integration tests for `ensure_default` (creates row, no-ops if exists), `find_by_user_id` (found/not found), `update` (overwrites values, updates `updated_at`)
- [x] 6.2 API tests for `GET /preferences` and `PUT /preferences`: authenticated success, 401 when logged out, 422 on invalid duration (zero/negative)

## 7. Frontend API client

- [x] 7.1 `frontend/src/api/preferences.ts` — `getPreferences()` and `updatePreferences(payload)` functions, following the fetch/error-handling pattern used in `frontend/src/api/auth.ts` or the vehicles API client

## 8. Frontend Preferences page

- [x] 8.1 `frontend/src/pages/PreferencesPage.tsx` — form with a number input for `default_ticket_duration_minutes` and a checkbox/toggle for `auto_create_ticket`, loads current values on mount, saves via `PUT /preferences`, shows saving/error state
- [x] 8.2 Add protected route `/preferences` in `App.tsx`, wrapped in `ProtectedRoute` like `/my-vehicles`

## 9. Frontend nav dropdown

- [x] 9.1 Rework `Nav.tsx`: replace the flat `My Vehicles` link + email + `Logout` button (when logged in) with a dropdown menu triggered by the user's email, containing `My Vehicles`, `Preferences`, and `Logout`
- [x] 9.2 Ensure dropdown is keyboard-accessible (opens/closes appropriately) and closes on outside click or item selection
- [x] 9.3 Confirm logged-out state is unaffected (still shows the Google login button, no dropdown)
- [x] 9.4 Use accessible, stable markup for the trigger and menu (e.g. a `button` with `aria-haspopup="true"`/`aria-expanded`, menu items exposed with `role="menuitem"` or as plain links inside a `role="menu"` container) so the dropdown can be targeted reliably by `getByRole` in Playwright without introducing ad-hoc `data-testid`s

## 10. i18n

- [x] 10.1 Add `nav.account` (dropdown trigger/aria-label if needed) and `nav.preferences` keys to `frontend/public/locales/en/translation.json` and `es/translation.json`
- [x] 10.2 Add a `page.preferences` section (title, field labels for duration and auto-create toggle, save button, saved/error messages) to both locale files

## 11. End-to-end tests (Playwright)

- [x] 11.1 Add `frontend/e2e/pages/NavPage.ts` — POM for the account dropdown: `accountTrigger` locator (the email button), `myVehiclesLink`, `preferencesLink`, `logoutButton`, and an `open()` helper that clicks the trigger and waits for the menu to be visible
- [x] 11.2 Adapt `frontend/e2e/my-vehicles.spec.ts`'s existing `"Navigation"` describe block (`"shows My Vehicles link in nav when logged in"` / `"does not show My Vehicles link when logged out"`, currently asserting `getByRole("link", { name: "My Vehicles" })` directly): since `My Vehicles` moves from a top-level link into the dropdown, these tests must open the account menu via `NavPage` first before asserting the link's visibility (and for the logged-out case, assert the account trigger itself is absent rather than asserting the link alone)
- [x] 11.3 Add nav dropdown coverage (extend the same `"Navigation"` describe block or a new `frontend/e2e/nav.spec.ts`):
  - clicking the email trigger opens the dropdown, revealing `My Vehicles`, `Preferences`, and `Logout`
  - the dropdown closes after selecting a link and on outside click
  - a logged-out visitor sees no account trigger/dropdown, only the Google login button
- [x] 11.4 Add `frontend/e2e/preferences.spec.ts` (mocking `GET`/`PUT /api/preferences`, following the `mockVehicleApis` route-mocking style from `my-vehicles.spec.ts`), covering:
  - unauthenticated visitor navigating to `/preferences` is redirected to `/` (mirrors the existing `"Auth guard"` describe block for `/my-vehicles`)
  - logged-in user sees the current values (mock returns `default_ticket_duration_minutes: 60`, `auto_create_ticket: false`) on page load
  - logged-in user changes the duration and toggle, saves, and sees the updated values reflected (mock `PUT` responding with the new values)
  - submitting an invalid duration (e.g. `0`) shows a validation error and does not call `PUT`, or the mock `PUT` returns 422 and the page surfaces the error without losing the entered values
- [x] 11.5 Add a `frontend/e2e/pages/PreferencesPage.ts` POM (duration input, auto-create toggle, save button, error/success locators), following the same constructor/locator pattern as `MyVehiclesPage.ts`

## 12. Verification

- [x] 12.1 Run backend test suite and linters (ruff, mypy) per project convention
- [x] 12.2 Run frontend lint/typecheck/build
- [x] 12.3 Run the full Playwright suite (`my-vehicles.spec.ts`, `map.spec.ts`, `nav.spec.ts`/updated nav tests, `preferences.spec.ts`) and confirm no regressions from the nav rework — `my-vehicles.spec.ts`, `nav.spec.ts`, and `preferences.spec.ts` all pass (34/34); `map.spec.ts`'s 3 tests fail only because they hit the real backend (`/api/parking/ser-zones`) which is not running in this environment — pre-existing environment dependency, unrelated to the nav rework (confirmed Nav.tsx changes did not regress any of the 34 passing tests)
- [x] 12.4 Manually verify: fresh login creates a preferences row with defaults (60, false); existing user without a row gets one on next login; GET/PUT roundtrip works; preferences page and nav dropdown are only visible when logged in
