## ADDED Requirements

### Requirement: ESLint is configured for TypeScript and React
The frontend SHALL have an `eslint.config.js` flat-config file at `frontend/eslint.config.js` using `@typescript-eslint/eslint-plugin` and `eslint-plugin-react-hooks`. The `package.json` SHALL expose a `lint` script running `eslint src/` and a `type-check` script running `tsc --noEmit`.

#### Scenario: No lint errors on clean code
- **WHEN** the frontend source files conform to ESLint rules
- **THEN** `pnpm lint` exits with code 0

#### Scenario: Lint violation fails the script
- **WHEN** a source file contains an ESLint error
- **THEN** `pnpm lint` exits with a non-zero code

#### Scenario: No type errors on clean code
- **WHEN** all TypeScript source files are type-correct
- **THEN** `pnpm type-check` exits with code 0

#### Scenario: Type error fails the script
- **WHEN** a source file contains a TypeScript type error
- **THEN** `pnpm type-check` exits with a non-zero code

---

### Requirement: CI workflow includes a lint-frontend job
The CI workflow SHALL include a `lint-frontend` job that runs on `ubuntu-latest`, installs pnpm via `pnpm/action-setup@v4`, installs frontend dependencies with `pnpm install --frozen-lockfile` from the `frontend/` working directory, and then runs `pnpm type-check` and `pnpm lint` sequentially. The job SHALL fail if either command exits with a non-zero code.

#### Scenario: Frontend type-check and lint pass on a clean PR
- **WHEN** all frontend TypeScript and ESLint rules are satisfied
- **THEN** the `lint-frontend` job exits with code 0 and the PR check passes

#### Scenario: TypeScript error fails the lint-frontend job
- **WHEN** a PR introduces a TypeScript type error
- **THEN** `pnpm type-check` exits non-zero, the `lint-frontend` job fails, and the PR check is marked failed

#### Scenario: ESLint error fails the lint-frontend job
- **WHEN** a PR introduces an ESLint rule violation
- **THEN** `pnpm lint` exits non-zero, the `lint-frontend` job fails, and the PR check is marked failed

---

### Requirement: CI workflow includes a test-frontend job running Playwright e2e
The CI workflow SHALL include a `test-frontend` job that runs on `ubuntu-latest`, installs pnpm, installs frontend dependencies with `--frozen-lockfile`, installs Playwright Chromium with `pnpm exec playwright install --with-deps chromium`, and runs `pnpm exec playwright test`. The `playwright.config.ts` SHALL define a `webServer` block that starts the Vite dev server (`pnpm dev`) and waits for `http://localhost:5173` with a 30-second timeout.

#### Scenario: All Playwright tests pass
- **WHEN** the Vite dev server starts successfully and all e2e scenarios pass
- **THEN** the `test-frontend` job exits with code 0 and the PR check passes

#### Scenario: A Playwright test fails
- **WHEN** any e2e test assertion fails
- **THEN** `playwright test` exits non-zero, the `test-frontend` job fails, and the PR check is marked failed

#### Scenario: Dev server auto-started by Playwright
- **WHEN** the `test-frontend` job starts and no server is already listening on port 5173
- **THEN** Playwright starts `pnpm dev` automatically and waits up to 30 seconds before running tests

#### Scenario: Chromium is available in CI
- **WHEN** the `test-frontend` job runs `pnpm exec playwright install --with-deps chromium`
- **THEN** Chromium and its system dependencies are installed and available for Playwright to use
