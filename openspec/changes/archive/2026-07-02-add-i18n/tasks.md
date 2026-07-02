## 1. Install Dependencies

- [x] 1.1 Add `i18next`, `react-i18next`, `i18next-browser-languagedetector`, and `i18next-http-backend` to `frontend/package.json` dependencies and run `npm install` inside `frontend/`

## 2. Translation Files

- [x] 2.1 Create `frontend/public/locales/en/translation.json` with all English strings per the key inventory in `design.md`
- [x] 2.2 Create `frontend/public/locales/es/translation.json` with all Spanish translations for the same key set

## 3. i18next Configuration

- [x] 3.1 Create `frontend/src/i18n.ts` — configure i18next with `HttpBackend`, `LanguageDetector`, supported languages `['en', 'es']`, fallback `'en'`, and `public/locales/{{lng}}/{{ns}}.json` as the backend load path
- [x] 3.2 Import `./i18n` in `frontend/src/main.tsx` before the `<App>` render so i18next initialises before any component mounts

## 4. Language Selector in Nav

- [x] 4.1 Update `frontend/src/components/Nav.tsx` to import `useTranslation` and `i18next`, replace all hardcoded strings with `t()` calls, and add a `<select>` language switcher that calls `i18next.changeLanguage(val)` on change with the current `i18next.language` pre-selected

## 5. Component String Replacement

- [x] 5.1 Update `frontend/src/pages/LandingPage.tsx` — replace hardcoded title with `t('page.landing.title')`
- [x] 5.2 Update `frontend/src/pages/MyVehiclesPage.tsx` — replace all hardcoded strings (title, "Add Vehicle", loading state, empty state, error) with `t()` calls
- [x] 5.3 Update `frontend/src/pages/MapPage.tsx` — replace `"Cargando zonas…"` and `"Failed to load map data"` with `t()` calls using `page.map.loading` and the existing error passthrough pattern
- [x] 5.4 Update `frontend/src/components/AddVehicleModal.tsx` — replace all labels, button text, placeholder options, and error strings with `t()` calls
- [x] 5.5 Update `frontend/src/components/EditVehicleModal.tsx` — replace all labels, button text, and error strings with `t()` calls; use `t('modal.editVehicle.keepBlank')` for the password hint
- [x] 5.6 Update `frontend/src/components/VehicleCard.tsx` — replace all field labels, button text, "No location data" placeholder, and `window.confirm` message with `t()` calls; use `t('vehicle.confirmDelete', { name: vehicle.display_name })` for the confirm dialog

## 6. Playwright Test Fixtures

- [x] 6.1 Update `frontend/e2e/fixtures/auth.ts` to set `localStorage.setItem('i18nextLng', 'en')` via `page.evaluate()` before any navigation, so E2E tests always run in English

## 7. Verification

- [x] 7.1 Run `npm run lint` and `npm run type-check` inside `frontend/` — no errors
- [x] 7.2 Run `npx playwright test` inside `frontend/` — all existing E2E tests pass
- [ ] 7.3 Start the dev server (`npm run dev`) and manually verify the language selector in Nav switches between English and Spanish, and that the chosen language persists on page reload
