## Context

The project has a Python/FastAPI backend with full CI coverage (ruff, mypy, pytest) and a React/TypeScript/Vite frontend with no CI coverage at all. The CI workflow (`ci.yml`) has generic job names (`lint`, `test`) that don't identify which component they cover. The release workflow (`release.yml`) builds a single Docker image without naming it by component. There is also no ESLint configuration in the frontend today.

## Goals / Non-Goals

**Goals:**
- Add `lint-frontend` and `test-frontend` jobs to `ci.yml`, run on every PR
- Rename existing jobs to `lint-backend` and `test-backend`
- Add ESLint (TypeScript-aware) to the frontend and expose it as `pnpm lint`
- Add type-check via `tsc --noEmit` exposed as `pnpm type-check`
- Wire Playwright e2e tests to run in CI with auto-started dev server
- Rename existing Docker image to `personal-mobility-manager-backend`
- Add `personal-mobility-manager-frontend` image built from `Dockerfile.frontend` in `release.yml`

**Non-Goals:**
- Unit/component testing for the frontend (Playwright covers e2e only; no Vitest setup)
- Code coverage reporting for the frontend
- Caching pnpm node_modules across runs (can be added later)
- Separate workflow files per component

## Decisions

### 1. ESLint flat config (v9 format)

Use `eslint.config.js` (flat config) with `@typescript-eslint/eslint-plugin` and `eslint-plugin-react-hooks`. This is the current ESLint v9 standard and avoids deprecated `.eslintrc.*` formats. Alternative: `oxlint` (faster, Rust-based) — rejected because ESLint has broader rule coverage and better TS integration for a new setup.

### 2. `pnpm type-check` script using `tsc --noEmit`

Add a `type-check` script to `package.json` that runs `tsc --noEmit`. The `lint-frontend` job runs both `pnpm type-check` and `pnpm lint` as sequential steps. This separates type errors from style violations in job output.

### 3. Playwright with `webServer` config

Add a `webServer` block to `playwright.config.ts` that runs `pnpm dev` and waits for `http://localhost:5173`. Playwright launches and tears down the dev server automatically. Alternative: start the dev server as a background step in the CI job — rejected because Playwright's native `webServer` handles port-ready detection and cleanup. `reuseExistingServer: !process.env.CI` prevents Playwright from killing a dev server the developer already has running locally.

### 4. Job naming: `-backend` / `-frontend` suffix

All CI jobs get an explicit suffix: `lint-backend`, `test-backend`, `lint-frontend`, `test-frontend`. This makes the `workflow_call` usage in `release.yml` readable and distinguishes component failures in the GitHub UI. Alternative: separate workflow files per component — rejected; the single `ci.yml` with `workflow_call` is already the established pattern.

### 5. Two parallel Docker jobs in `release.yml`

Add `docker-backend` and `docker-frontend` jobs, both depending on `ci` and running in parallel. Images pushed to:
- `ghcr.io/jmalvarezf-lmes/personal-mobility-manager-backend`
- `ghcr.io/jmalvarezf-lmes/personal-mobility-manager-frontend`

Alternative: a single job that builds both — rejected because parallel jobs are faster and Docker build failures are easier to triage per component.

## Risks / Trade-offs

- **Playwright Chrome in CI**: Playwright requires Chromium to be installed. The `test-frontend` job must run `pnpm exec playwright install --with-deps chromium` before running tests. Missed step → cryptic "browser not found" error.
- **pnpm not pre-installed on `ubuntu-latest`**: Must use `pnpm/action-setup@v4` to install pnpm before any `pnpm` command. Existing backend jobs are unaffected (they use pip).
- **Dev server startup time**: Vite dev server is fast but not instant; Playwright's `webServer.timeout` should be set to ~30 s to avoid flaky CI on slow runners.
- **ESLint rules strictness**: Starting with recommended rules only (`@typescript-eslint/recommended`, `react-hooks/recommended`). Too strict a ruleset on a first-time lint setup will fail the CI immediately. Can tighten rules in a follow-up change.
- **Image rename is a breaking change for consumers**: `personal-mobility-manager` → `personal-mobility-manager-backend`. Any external system pulling the old tag will break. Mitigation: document the rename in the PR description.

## Migration Plan

1. Add ESLint config and `pnpm lint` / `pnpm type-check` scripts — verify locally first.
2. Update `playwright.config.ts` with `webServer` block.
3. Update `ci.yml`: rename backend jobs, add frontend jobs.
4. Update `release.yml`: rename Docker job and image tag, add frontend Docker job.
5. Open PR — all four CI jobs must pass before merge.
6. Merge to `main` triggers two Docker image pushes.

Rollback: revert `ci.yml` and `release.yml` to previous state; the frontend ESLint config is additive and safe to keep.
