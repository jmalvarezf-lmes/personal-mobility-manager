## MODIFIED Requirements

### Requirement: Lint job runs ruff and mypy
The CI workflow SHALL include a `lint-backend` job (renamed from `lint`) that runs `ruff check src/ tests/` and `mypy src/`. Both tools SHALL be installed from `requirements-dev.txt`. The job SHALL fail if either tool reports errors.

#### Scenario: Clean code passes lint
- **WHEN** all source files conform to ruff and mypy rules
- **THEN** the `lint-backend` job exits with code 0

#### Scenario: Lint violation fails the job
- **WHEN** a file contains a ruff or mypy error
- **THEN** the `lint-backend` job exits with a non-zero code and the PR check is marked failed

---

### Requirement: Test job runs the full test suite with a live PostgreSQL instance
The CI workflow SHALL include a `test-backend` job (renamed from `test`) that declares a `postgres:16-alpine` service container with health-check (`pg_isready`). The job SHALL set `POSTGRES_DSN` from the service container's connection details, run `alembic upgrade head` before executing `pytest`, and collect coverage output.

#### Scenario: All tests pass including integration
- **WHEN** the PostgreSQL service is healthy and `POSTGRES_DSN` is set
- **THEN** `pytest tests/` runs all test layers (unit, integration, e2e) and exits with code 0

#### Scenario: PostgreSQL service not yet healthy
- **WHEN** the postgres service container is still starting
- **THEN** the job waits until the health check passes before running any steps

#### Scenario: A test fails
- **WHEN** any test in the suite fails
- **THEN** the `test-backend` job exits with a non-zero code and the PR check is marked failed

#### Scenario: Schema applied before tests
- **WHEN** the `test-backend` job starts
- **THEN** `alembic upgrade head` runs successfully before `pytest` is invoked, ensuring the `ser_zones` table exists
