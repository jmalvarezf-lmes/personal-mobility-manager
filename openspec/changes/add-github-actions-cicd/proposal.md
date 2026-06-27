## Why

The project has no automated quality gate on pull requests and no delivery pipeline — every merge to `main` and every release requires manual steps to build and push the Docker image. Introducing GitHub Actions gives every PR a pass/fail signal before code lands, and automates image delivery to GitHub Container Registry on merge and release.

## What Changes

- Add `.github/workflows/ci.yml`: runs on every pull request; executes lint (`ruff` + `mypy`) and the full test suite (unit, integration, e2e) with a PostgreSQL 16 service container so integration tests are never skipped.
- Add `.github/workflows/release.yml`: runs on push to `main` and on semver tags (`v*.*.*`); reuses `ci.yml` via `workflow_call`, then builds and pushes the Docker image to `ghcr.io` with environment-appropriate tags.
- Image tagging strategy: push to `main` → `:latest` + `:sha`; push tag `v1.2.3` → `:1.2.3`, `:1.2`, `:1`, `:latest`.
- No changes to `docker-compose.yml` — it remains the local development stack.

## Capabilities

### New Capabilities

- `ci-pipeline`: Pull-request quality gate. Covers the `ci.yml` workflow: lint job (ruff + mypy) and test job (pytest with postgres service container, alembic migrations applied before tests run).
- `release-pipeline`: Automated Docker image delivery. Covers the `release.yml` workflow: CI reuse via `workflow_call`, Docker build, semver/SHA tagging, and push to `ghcr.io/jmalvarezf-lmes/personal-mobility-manager`.

### Modified Capabilities

## Impact

- `.github/workflows/ci.yml` — new file
- `.github/workflows/release.yml` — new file
- No application code changes
- No `docker-compose.yml` changes
- Registry: `ghcr.io/jmalvarezf-lmes/personal-mobility-manager` (GitHub Packages, free for public repos, authenticated via `GITHUB_TOKEN` — no manual secrets required)
