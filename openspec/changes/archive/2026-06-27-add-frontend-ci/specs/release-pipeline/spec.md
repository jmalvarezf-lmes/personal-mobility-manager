## MODIFIED Requirements

### Requirement: Release workflow reuses the CI pipeline before building
The release workflow SHALL invoke `.github/workflows/ci.yml` via `workflow_call` and SHALL only proceed to Docker build jobs if the CI job succeeds.

#### Scenario: CI passes, Docker builds proceed
- **WHEN** the `ci.yml` workflow_call job completes successfully
- **THEN** both the backend and frontend Docker build and push jobs start

#### Scenario: CI fails, Docker builds are skipped
- **WHEN** the `ci.yml` workflow_call job fails
- **THEN** neither Docker build job runs and the release workflow fails

---

### Requirement: Backend Docker image is built and pushed to ghcr.io
The release workflow SHALL include a `docker-backend` job that builds the Docker image from the project `Dockerfile` and pushes it to `ghcr.io/jmalvarezf-lmes/personal-mobility-manager-backend`. Authentication SHALL use `GITHUB_TOKEN`. The build SHALL use `docker/build-push-action` with `docker/metadata-action` for tag computation.

#### Scenario: Backend image pushed on main merge
- **WHEN** a commit is pushed to `main`
- **THEN** the backend image is pushed with tags `:latest` and `:<short-sha>` to `ghcr.io/jmalvarezf-lmes/personal-mobility-manager-backend`

#### Scenario: Backend image pushed on semver tag
- **WHEN** a tag `v1.2.3` is pushed
- **THEN** the backend image is pushed with tags `:1.2.3`, `:1.2`, `:1`, and `:latest` to `ghcr.io/jmalvarezf-lmes/personal-mobility-manager-backend`

#### Scenario: Authentication via GITHUB_TOKEN
- **WHEN** the release workflow runs
- **THEN** it logs in to `ghcr.io` using `secrets.GITHUB_TOKEN` with no additional secrets configured

---

### Requirement: Frontend Docker image is built and pushed to ghcr.io
The release workflow SHALL include a `docker-frontend` job that builds the Docker image from `Dockerfile.frontend` and pushes it to `ghcr.io/jmalvarezf-lmes/personal-mobility-manager-frontend`. Authentication SHALL use `GITHUB_TOKEN`. The build SHALL use `docker/build-push-action` with `docker/metadata-action` for tag computation. The `docker-frontend` job SHALL run in parallel with `docker-backend` (both depend only on `ci`).

#### Scenario: Frontend image pushed on main merge
- **WHEN** a commit is pushed to `main`
- **THEN** the frontend image is pushed with tags `:latest` and `:<short-sha>` to `ghcr.io/jmalvarezf-lmes/personal-mobility-manager-frontend`

#### Scenario: Frontend image pushed on semver tag
- **WHEN** a tag `v1.2.3` is pushed
- **THEN** the frontend image is pushed with tags `:1.2.3`, `:1.2`, `:1`, and `:latest` to `ghcr.io/jmalvarezf-lmes/personal-mobility-manager-frontend`

#### Scenario: Frontend and backend images built in parallel
- **WHEN** the CI job succeeds and a release trigger fires
- **THEN** `docker-backend` and `docker-frontend` jobs start concurrently, each building its own image independently
