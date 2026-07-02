## Why

All UI strings are hardcoded in English, making the app inaccessible to Spanish-speaking users and hard to extend to other languages. Adding i18n now — while the string surface is small (~45 strings across 6 components) — is cheaper than retrofitting a larger codebase later.

## What Changes

- Install `i18next`, `react-i18next`, `i18next-browser-languagedetector`, and `i18next-http-backend` as frontend dependencies.
- Add translation files for English (`en`) and Spanish (`es`) under `frontend/public/locales/`.
- Configure i18next to detect the browser language automatically and fall back to English.
- Replace all hardcoded UI strings in Nav, LandingPage, MyVehiclesPage, MapPage, AddVehicleModal, EditVehicleModal, and VehicleCard with `t()` calls.
- Add a language selector `<select>` in the Nav that shows the currently detected language and allows the user to override it (persisted in `localStorage`).
- Fix the pre-existing mixed-language bug in `MapPage.tsx` (`"Cargando zonas…"` hardcoded in Spanish).
- Force `lng=en` in Playwright E2E fixtures so tests are always in English regardless of the test environment's browser locale.
- Backend API error messages are left untranslated (displayed as-is from the server).

## Capabilities

### New Capabilities

- `ui-i18n`: Browser language detection, English/Spanish translation files, language switcher in Nav, `t()` calls across all components.

### Modified Capabilities

- `vehicle-management-ui`: UI strings are now translated; component behavior is unchanged.
- `landing-page`: Title string is now translated; page structure is unchanged.

## Impact

- **Frontend dependencies**: 4 new npm packages added.
- **Frontend components**: Nav, LandingPage, MyVehiclesPage, MapPage, AddVehicleModal, EditVehicleModal, VehicleCard — string literals replaced.
- **New files**: `frontend/src/i18n.ts`, `frontend/public/locales/en/translation.json`, `frontend/public/locales/es/translation.json`.
- **E2E tests**: `frontend/e2e/fixtures/auth.ts` updated to force `lng=en` via `localStorage`.
- **No backend changes** required.
- **No breaking API changes**.
