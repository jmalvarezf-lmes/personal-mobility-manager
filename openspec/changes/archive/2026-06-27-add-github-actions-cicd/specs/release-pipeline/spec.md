## ADDED Requirements

### Requirement: Release workflow triggers on main push, semver tags, and manual dispatch
A GitHub Actions workflow file SHALL exist at `.github/workflows/release.yml` and SHALL be triggered on push to the `main` branch, on push of tags matching `v*.*.*`, and on `workflow_dispatch` (manual trigger from the GitHub Actions UI).

#### Scenario: Merge to main triggers release workflow
- **WHEN** a pull request is merged into `main`
- **THEN** the release workflow starts automatically

#### Scenario: Semver tag triggers release workflow
- **WHEN** a tag matching `v*.*.*` (e.g., `v1.2.3`) is pushed
- **THEN** the release workflow starts automatically

#### Scenario: Manual dispatch triggers release workflow
- **WHEN** a user clicks "Run workflow" on the Actions tab in the GitHub UI
- **THEN** the release workflow starts immediately against the selected branch or tag

---

### Requirement: Release workflow reuses the CI pipeline before building
The release workflow SHALL invoke `.github/workflows/ci.yml` via `workflow_call` and SHALL only proceed to the Docker build job if the CI job succeeds.

#### Scenario: CI passes, Docker build proceeds
- **WHEN** the `ci.yml` workflow_call job completes successfully
- **THEN** the Docker build and push job starts

#### Scenario: CI fails, Docker build is skipped
- **WHEN** the `ci.yml` workflow_call job fails
- **THEN** the Docker build and push job does not run and the release workflow fails

---

### Requirement: Docker image is built and pushed to ghcr.io
The release workflow SHALL build the Docker image from the project `Dockerfile` and push it to `ghcr.io/jmalvarezf-lmes/personal-mobility-manager`. Authentication SHALL use `GITHUB_TOKEN` (no manually configured secrets). The build SHALL use `docker/build-push-action` with `docker/metadata-action` for tag computation.

#### Scenario: Image pushed on main merge
- **WHEN** a commit is pushed to `main`
- **THEN** the image is pushed with tags `:latest` and `:<short-sha>`

#### Scenario: Image pushed on semver tag
- **WHEN** a tag `v1.2.3` is pushed
- **THEN** the image is pushed with tags `:1.2.3`, `:1.2`, `:1`, and `:latest`

#### Scenario: Authentication via GITHUB_TOKEN
- **WHEN** the release workflow runs
- **THEN** it logs in to `ghcr.io` using `secrets.GITHUB_TOKEN` with no additional secrets configured

---

### Requirement: Package visibility matches repository visibility
The GitHub Package produced by the release workflow SHALL be public, matching the public visibility of the repository, so that images can be pulled without authentication.

#### Scenario: Image pullable without authentication
- **WHEN** the image has been pushed to `ghcr.io`
- **THEN** `docker pull ghcr.io/jmalvarezf-lmes/personal-mobility-manager:latest` succeeds without credentials
