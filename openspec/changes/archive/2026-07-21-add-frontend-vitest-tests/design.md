## Context

The frontend (`frontend/`, React 19 + Vite 8 + TypeScript) has only Playwright e2e coverage (`@playwright/test`, tests under `frontend/e2e/`). Three prior OpenSpec changes hit this gap directly:

- `add-ambient-label-lookup`: component/story coverage for `AmbientLabelIcon`'s three render states was left unchecked — "no frontend unit-test runner or Storybook configured."
- `add-vehicle-location-history`: frontend unit tests skipped entirely; only `tsc`/`eslint`/`vite build` ran.
- `add-user-timezone-preference`: pure-function assertions for `src/utils/timezone.ts` were written as `frontend/e2e/timezone-utils.spec.ts` — real unit tests, executed under Playwright's Node-side test runner (no browser/`page`) purely because no vitest/jest existed and design.md for that change forbade adding a new dependency.

A live-testing regression on that same change (a broken `PreferencesPage` timezone combobox: the search input didn't re-filter, and Enter submitted the whole form) is exactly the class of bug pure-function tests can't catch — it's component interaction behavior, not logic extractable into a plain function.

This change adds Vitest + `jsdom` + React Testing Library, migrates the Playwright workaround into a real unit test, and adds new unit/component tests for previously-uncovered modules. **No `frontend/src` application code changes** — this is test files, test config, and CI wiring only.

## Goals / Non-Goals

**Goals:**
- Stand up Vitest as the frontend unit-test runner, in `jsdom` mode, integrated with the existing Vite config.
- Provide a reusable component-test harness (render helper + provider wrapping) so future component tests don't each reinvent i18n/router/auth setup.
- Cover the pure-logic modules with no prior tests: `src/utils/timezone.ts` (migrated from the Playwright workaround), `src/api/*.ts` (URL/param construction, error branches, body serialization), `src/components/notificationChannels/registry.ts`.
- Cover the components with the richest documented/observed behavior: `PreferencesPage`'s timezone combobox (regression coverage for the bug described above), `VehicleCard`'s ambient-label render states, `AmbientLabelIcon`.
- Add a `unit-test-frontend` CI job that runs the suite without a live backend, mirroring `lint-frontend`'s shape.

**Non-Goals:**
- No coverage threshold/gate (e.g., `--coverage` enforcement in CI) — this change adds the runner and meaningful tests, not a coverage policy. Can be a follow-up.
- No full component-test coverage of every page/component in one pass — `VehicleMap`/`ZoneMap` (Leaflet-heavy, need canvas/DOM APIs `jsdom` doesn't implement) and full-page integration tests (`MapPage`, `MyVehiclesPage` end-to-end flows) are explicitly out of scope; that's what the existing Playwright e2e suite already covers.
- No changes to `frontend/e2e/*` behavior or coverage beyond removing the one workaround file (`timezone-utils.spec.ts`) whose content is being migrated, not dropped.
- No changes to any `frontend/src` production code, `translation.json` files, or API contracts.

## Decisions

**Vitest config lives inside `vite.config.ts`, not a separate `vitest.config.ts`.** Using `defineConfig` from `vitest/config` (which re-exports and merges Vite's `defineConfig` with a `test` field) avoids maintaining two configs that could drift on plugins (`@vitejs/plugin-react`, `@tailwindcss/vite`). A single `/// <reference types="vitest/config" />` triple-slash directive at the top of `vite.config.ts` provides the `test` field's types.

**`jsdom` over `happy-dom`.** `jsdom` is the de facto standard, has the broadest API coverage, and is what React Testing Library's own docs assume. `happy-dom` is faster but has more DOM-API gaps; given the small test count expected here, jsdom's speed cost is negligible and its compatibility is worth more.

**A shared test-render helper (`src/test/render.tsx`) wraps `I18nextProvider` and `MemoryRouter`/`AuthProvider` as needed, rather than each test file setting up providers ad hoc.** Components under test call `useTranslation()` (react-i18next) and some call `useAuth()` (via `Nav`, which several page components render). Reproducing that setup per test file would be repetitive and drift-prone; a single helper keeps provider wiring in one place.

**A dedicated, synchronous test i18n instance (`src/test/i18n.ts`) — not the app's real `src/i18n.ts`.** Production i18n uses `i18next-http-backend`, which fetches `/locales/{{lng}}/{{ns}}.json` over HTTP — unavailable and undesirable in a `jsdom` unit test (no dev server, no network calls in unit tests). The test instance uses `initReactI18next` with the real `en/translation.json` resource bundle imported directly (no HTTP backend), so rendered text matches production strings without a network dependency. `es/translation.json` is not loaded in tests — component tests assert against English strings and/or `data-testid`/`role` selectors, not translated text specifically.

**`fetch` is stubbed per-test with `vi.stubGlobal("fetch", ...)`, not a library like MSW.** The `src/api/*.ts` layer is a thin, uniform `fetch` wrapper (no interceptor logic, no retry/queueing) — mocking `fetch` directly is simpler and keeps this change's dependency footprint to test-only additions already decided (Vitest + Testing Library). MSW is worth considering later if API mocking complexity grows, but is unnecessary scope for the current test set.

**`timezone-utils.spec.ts` is migrated, not duplicated.** Its content becomes `src/utils/timezone.test.ts` (colocated with the module, matching the convention every other new test file in this change follows), and the Playwright file is deleted. Keeping both would mean the same assertions run under two runners with no added confidence, and the file's own header comment already documents that Playwright was only ever a workaround.

**New CI job (`unit-test-frontend`), not a step inside `test-frontend`.** `test-frontend` boots a live Postgres + FastAPI backend to support Playwright's real network calls; Vitest's component tests mock `fetch` and need neither. Folding vitest into that job would tie a fast, backend-free suite to the slowest job in the pipeline. A new job shaped like `lint-frontend` (checkout → pnpm → node, no services) keeps it fast and keeps the backend-dependency boundary honest.

**Test files are colocated (`Foo.test.ts(x)` next to `Foo.ts(x)`), not under a separate `__tests__/` or `tests/` directory.** Matches the migrated `timezone.test.ts` placement and is Vitest's own convention; keeps a test next to the module it exercises.

## Risks / Trade-offs

- **[Risk] `jsdom` doesn't implement Canvas/WebGL/some geometry APIs Leaflet needs** → Mitigation: `VehicleMap`/`ZoneMap` are explicitly out of scope (Non-Goals); e2e already covers them.
- **[Risk] A parallel, hand-maintained test i18n resource bundle could drift from the real `en/translation.json` if keys are renamed** → Mitigation: the test i18n instance imports the real `en/translation.json` file directly (not a hand-copied subset), so it can't drift — a renamed key breaks both production and tests identically.
- **[Risk] `pnpm-lock.yaml` changes from new devDependencies could look like unrelated scope creep in review** → Mitigation: called out explicitly in proposal.md's Impact section; it's a mechanical lockfile update from `pnpm install`, not a hand edit.
- **[Trade-off] No coverage enforcement means nothing stops future PRs from adding untested code** → Accepted as a Non-Goal for this change; a coverage gate is a separate policy decision better made once there's a baseline to gate against.

## Migration Plan

1. Add devDependencies, Vitest config, `test` script — verify `pnpm test` runs (even with zero test files) before writing any tests.
2. Migrate `timezone-utils.spec.ts` → `timezone.test.ts` first (smallest, already-written assertions) to validate the jsdom/config setup end-to-end.
3. Add remaining pure-logic tests (`api/*.ts`, `registry.ts`), then component tests (`PreferencesPage`, `VehicleCard`, `AmbientLabelIcon`), building out the shared render helper and test i18n instance as needed by the first component test that requires them.
4. Add the `unit-test-frontend` CI job last, once `pnpm test` is green locally.
5. Rollback: revert the commit(s); no production code or data is touched, so rollback has no runtime impact.

## Open Questions

- None outstanding — component scope, config shape, and CI job shape are decided above. If future contributors want MSW-based API mocking or a coverage gate, that's a separate proposal.
