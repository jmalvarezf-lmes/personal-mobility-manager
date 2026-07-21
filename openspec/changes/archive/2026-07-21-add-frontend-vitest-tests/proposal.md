## Why

The frontend has no unit-test runner: only Playwright e2e (`@playwright/test`) exists. This has already blocked or distorted test coverage on three prior changes — `add-ambient-label-lookup` left component coverage unchecked as blocked, `add-vehicle-location-history` skipped frontend tests entirely, and `add-user-timezone-preference` smuggled pure-function assertions into Playwright's Node-side runner (`frontend/e2e/timezone-utils.spec.ts`) as a workaround. The most recent regression on this codebase — a broken `PreferencesPage` timezone combobox (search input not re-filtering, Enter submitting the form) — was a component-interaction bug that only manual testing caught; a component-level unit test would have caught it as a regression before it shipped.

## What Changes

- Add `vitest` + `jsdom` + `@testing-library/react` (+ `@testing-library/jest-dom`, `@testing-library/user-event`) as frontend devDependencies. No production dependency changes.
- Add a Vitest config (extending `vite.config.ts` or a sibling `vitest.config.ts`) with a `jsdom` environment, and a `test` script in `frontend/package.json`.
- Migrate the existing Playwright-workaround unit tests in `frontend/e2e/timezone-utils.spec.ts` into a real Vitest suite (`src/utils/timezone.test.ts`), and remove the workaround file. No behavior change to `timezone.ts` itself.
- Add new Vitest unit tests for pure-logic modules with no prior coverage: `src/api/*.ts` (URL/param construction, error-status handling, body serialization) and `src/components/notificationChannels/registry.ts`.
- Add new Vitest + Testing Library component tests for previously-uncovered interactive components, prioritizing the ones with the richest documented/observed behavior: the `PreferencesPage` timezone combobox (the exact regression class described above), `VehicleCard`'s ambient-label rendering states, and `AmbientLabelIcon`.
- Add a new `unit-test-frontend` job to `.github/workflows/ci.yml`, shaped like the existing `lint-frontend` job (checkout → pnpm → node, no backend/Postgres required) running `pnpm test`.
- **No application/production code in `frontend/src` changes.** This change is test code, test tooling config, and CI wiring only.

## Capabilities

### New Capabilities
- `frontend-unit-testing`: Vitest + Testing Library unit/component test infrastructure for the frontend — test runner config, `jsdom` environment, and coverage expectations for pure-logic modules and interactive components.

### Modified Capabilities
- `frontend-ci`: adds a new `unit-test-frontend` CI job requirement (parallel to the existing `lint-frontend` and `test-frontend` jobs) that runs the Vitest suite without a live backend.

## Impact

- **Affected code**: `frontend/package.json`, `frontend/pnpm-lock.yaml`, new Vitest config file, new `*.test.ts(x)` files colocated with the modules they cover, `frontend/e2e/timezone-utils.spec.ts` (removed), `.github/workflows/ci.yml`.
- **Not affected**: any file under `frontend/src` other than adding test files — no component, page, util, or API logic changes.
- **Dependencies**: adds `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event` as devDependencies.
- **CI**: adds one new job; existing `lint-frontend` and `test-frontend` (Playwright) jobs are unchanged.
