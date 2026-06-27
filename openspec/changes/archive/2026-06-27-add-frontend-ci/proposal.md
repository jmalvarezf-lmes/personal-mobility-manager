## Why

The frontend (React/TypeScript/Vite) has no CI checks — linting, type-checking, and tests run only locally, so broken code can merge. Meanwhile the existing CI and Docker jobs don't distinguish backend from frontend, making it ambiguous what each artifact is. Parity across both components is needed to keep quality gates consistent.

## What Changes

- **Add `tsc --noEmit` type-check + ESLint linter job** for the frontend in `ci.yml`, triggered on every PR.
- **Add Playwright e2e test job** for the frontend in `ci.yml`, triggered on every PR.
- **Rename existing Python CI jobs** from `lint` / `test` to `lint-backend` / `test-backend` in `ci.yml`.
- **Build and push a `frontend` Docker image** (`Dockerfile.frontend`) to `ghcr.io` in `release.yml`, alongside the existing backend image, on merge to `main` and on semver tags.
- **Rename existing Docker image** from `personal-mobility-manager` to `personal-mobility-manager-backend` in `release.yml` and the Docker metadata step.
- **Add ESLint** to the frontend `package.json` devDependencies and add a `lint` script (ESLint is not currently configured).

## Capabilities

### New Capabilities

- `frontend-ci`: CI checks (type-check, lint, e2e tests) for the React/TypeScript frontend, run on every pull request.

### Modified Capabilities

- `ci-pipeline`: Existing backend lint and test jobs renamed with `-backend` suffix; new `lint-frontend` and `test-frontend` jobs added.
- `release-pipeline`: Backend Docker image renamed to `personal-mobility-manager-backend`; new `personal-mobility-manager-frontend` image built and pushed from `Dockerfile.frontend`.

## Impact

- `.github/workflows/ci.yml` — add 2 frontend jobs, rename 2 backend jobs
- `.github/workflows/release.yml` — rename backend Docker step, add frontend Docker build/push step
- `frontend/package.json` — add `eslint`, `@typescript-eslint/eslint-plugin`, `@typescript-eslint/parser` devDependencies; add `lint` script
- `frontend/eslint.config.js` (new) — ESLint flat config for TypeScript + React
- `frontend/playwright.config.ts` — add `webServer` config so Playwright can start the dev server in CI
