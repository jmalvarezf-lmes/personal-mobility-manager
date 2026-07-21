## ADDED Requirements

### Requirement: CI workflow includes a unit-test-frontend job running Vitest
The CI workflow SHALL include a `unit-test-frontend` job that runs on `ubuntu-latest`, installs pnpm via `pnpm/action-setup`, installs frontend dependencies with `pnpm install --frozen-lockfile` from the `frontend/` working directory, and then runs `pnpm test`. This job SHALL NOT declare a `postgres` service or start the backend API — the Vitest suite mocks `fetch` and does not require a live backend.

#### Scenario: Vitest suite passes on a clean PR
- **WHEN** all Vitest unit and component tests pass
- **THEN** the `unit-test-frontend` job exits with code 0 and the PR check passes

#### Scenario: A Vitest test fails
- **WHEN** any Vitest test assertion fails
- **THEN** `pnpm test` exits non-zero, the `unit-test-frontend` job fails, and the PR check is marked failed

#### Scenario: No backend dependency
- **WHEN** the `unit-test-frontend` job runs
- **THEN** it completes without a `postgres` service container and without starting the backend API, unlike `test-frontend`
