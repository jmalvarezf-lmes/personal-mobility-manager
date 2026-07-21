## 1. Tooling setup

- [x] 1.1 Add `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event` as devDependencies in `frontend/package.json`; run `pnpm install` to update `frontend/pnpm-lock.yaml`.
- [x] 1.2 Add a Vitest `test` block to `frontend/vite.config.ts` using `defineConfig` from `vitest/config` (`jsdom` environment, `globals: true` or explicit imports — decide and note choice), with a `/// <reference types="vitest/config" />` directive.
- [x] 1.3 Add `frontend/src/test/setup.ts` (imports `@testing-library/jest-dom` matchers, runs `cleanup()` after each test) and wire it as the config's `setupFiles`.
- [x] 1.4 Add a `test` script (`vitest run`) to `frontend/package.json`.
- [x] 1.5 Verify `pnpm test` runs cleanly with zero test files (sanity-checks the config before writing any tests).

## 2. Shared test harness

- [x] 2.1 Add `frontend/src/test/i18n.ts`: a dedicated i18next instance via `initReactI18next`, loading `frontend/public/locales/en/translation.json` directly as an imported resource bundle (no `i18next-http-backend`).
- [x] 2.2 Add `frontend/src/test/render.tsx`: `renderWithProviders(ui, options?)` wrapping `I18nextProvider` (using the test i18n instance) and, where needed, `AuthProvider`/router context, returning Testing Library's standard render result.

## 3. Migrate the Playwright workaround

- [x] 3.1 Create `frontend/src/utils/timezone.test.ts` with the assertions currently in `frontend/e2e/timezone-utils.spec.ts` (resolution cascade, DST-aware CET/CEST abbreviation switch, unrecognized-zone UTC fallback), translated to Vitest's `describe`/`it`/`expect` API.
- [x] 3.2 Delete `frontend/e2e/timezone-utils.spec.ts`.
- [x] 3.3 Run `pnpm test` and confirm the migrated suite passes.

## 4. Pure-logic module coverage

- [x] 4.1 Add `frontend/src/api/vehicles.test.ts`: mock global `fetch`, cover each exported function's happy path (correct URL/method/headers/body) and non-OK-response error path (thrown `Error`, message includes response body text where applicable), including `getVehicleLocationHistory`'s `limit`/`offset` query-string construction.
- [x] 4.2 Add test coverage for the remaining `frontend/src/api/*.ts` modules (`auth.ts`, `cities.ts`, `notificationPreferences.ts`, `notifications.ts`, `preferences.ts`, `serTicketProviders.ts`, `zones.ts`), following the same mocked-`fetch` pattern — one `*.test.ts` per module, scoped to what each module actually exports.
- [x] 4.3 Add `frontend/src/components/notificationChannels/registry.test.ts` asserting `CONNECT_FLOW_REGISTRY` maps `"telegram"` to `TelegramConnectFlow` and that an unknown channel id is absent from the registry.

## 5. Component coverage

- [x] 5.1 Add `frontend/src/pages/PreferencesPage.test.tsx`: mock the `preferences`/`notifications` API modules; cover the timezone combobox live-filtering as the user types (regression test for the fixed "search input doesn't re-filter" bug) and Enter never triggering a form submit/save request (regression test for the fixed "Enter submits the form" bug), per `frontend/src/pages/PreferencesPage.tsx`'s current combobox implementation.
- [x] 5.2 Add `frontend/src/components/AmbientLabelIcon.test.tsx` covering its render states (icon shown / no-label indicator / nothing rendered), per the three states `add-ambient-label-lookup` left unchecked.
- [x] 5.3 Add `frontend/src/components/VehicleCard.test.tsx` covering ambient-label rendering across a vehicle with a label, a vehicle with none, and a vehicle with a `null` ambient label.

## 6. CI

- [x] 6.1 Add a `unit-test-frontend` job to `.github/workflows/ci.yml`, shaped like `lint-frontend` (checkout, pnpm setup, node setup, `pnpm install --frozen-lockfile`, `pnpm test`) — no `postgres` service, no backend startup steps.
- [x] 6.2 Verify the new job's steps run pnpm/node setup identically to `lint-frontend` (same action versions/cache config) so it doesn't drift from the existing frontend jobs' conventions.

## 7. Verification

- [x] 7.1 Run `pnpm test`, `pnpm type-check`, `pnpm lint`, and `pnpm exec playwright test` locally — all SHALL pass, confirming no production code was touched and nothing else regressed. (Playwright: 69/73 pass; the 4 `map.spec.ts` failures are pre-existing/environmental — the sandbox's Postgres has zero rows in `ser_zones`, i.e. the SER-zone ingestion job that fetches Madrid's open-data SHP file never ran in this environment. Confirmed unrelated to this change: `map.spec.ts` and zone ingestion are untouched by this change, and `select count(*) from ser_zones` returns 0.)
- [x] 7.2 Confirm `git diff` touches only: `frontend/package.json`, `frontend/pnpm-lock.yaml`, `frontend/vite.config.ts`, new `frontend/src/test/*` files, new colocated `*.test.ts(x)` files, the deleted `frontend/e2e/timezone-utils.spec.ts`, and `.github/workflows/ci.yml` — no other `frontend/src` file is modified. One additional necessary file beyond that list: `frontend/pnpm-workspace.yaml` (new) — see Deviations.
