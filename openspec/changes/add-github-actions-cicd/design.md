## Context

The project has no CI/CD pipeline. Quality checks (lint, tests) are run manually and Docker images are built and pushed manually. The repository is public on GitHub (`jmalvarezf-lmes/personal-mobility-manager`), making GitHub Actions and GitHub Packages (ghcr.io) the natural free-tier choice. The test suite is split into unit/e2e (no external deps) and integration (requires PostgreSQL); the Makefile already exposes `lint`, `test`, `db-migrate` targets. The Dockerfile uses an entrypoint script that runs `alembic upgrade head` before starting the server.

## Goals / Non-Goals

**Goals:**
- Automated lint + full test gate on every pull request (blocking merge on failure).
- Integration tests run in CI against a real PostgreSQL instance — never skipped.
- Automated Docker image build and push to `ghcr.io` on every merge to `main` and on every semver release tag.
- Semver-split image tags on release (`v1.2.3` → `:1`, `:1.2`, `:1.2.3`, `:latest`); SHA + latest on `main` push.
- `docker-compose.yml` remains unchanged — it is local dev only.

**Non-Goals:**
- Deployment to any environment (Kubernetes, VMs, etc.) — out of scope.
- Secrets rotation or environment-specific config management.
- Caching of pip packages beyond what GitHub Actions provides by default.
- Branch protection rule configuration (done in GitHub UI, not in files).

## Decisions

### D1 — Two workflow files, not one

**Decision**: `ci.yml` (PR gate) and `release.yml` (delivery) are separate files. `release.yml` reuses `ci.yml` via `workflow_call` instead of duplicating steps.

**Why**: A single file with `if:` guards on every step is hard to read and reason about. Two files have clear, single responsibilities. `workflow_call` avoids duplication while keeping the files independent.

**Alternatives considered**:
- One `pipeline.yml` with conditional steps — readable only for trivial pipelines; grows messy quickly.
- Duplicate lint/test steps in `release.yml` — simpler but creates drift risk if the CI job changes.

### D2 — PostgreSQL as a service container in CI

**Decision**: Declare `postgres:16-alpine` as a GitHub Actions service in the `test` job. Pass `POSTGRES_DSN` as a job env var. Run `alembic upgrade head` as a step before `pytest`.

**Why**: Integration tests are first-class — they must run in CI, not just locally. Service containers are ephemeral and isolated per job run, which is exactly what we need.

**Alternatives considered**:
- Skip integration tests in CI — rejected; this defeats their purpose.
- Use `docker-compose up` — adds complexity; service containers are the native Actions approach.

### D3 — `docker/metadata-action` for image tagging

**Decision**: Use the official `docker/metadata-action` to compute image tags from the git context automatically.

**Why**: Semver splitting (v1.2.3 → 1, 1.2, 1.2.3) and SHA extraction are non-trivial shell logic. `metadata-action` handles all edge cases and is maintained by Docker. Configuration is declarative.

**Alternatives considered**:
- Hand-written shell tag computation — fragile and verbose.

### D4 — `GITHUB_TOKEN` for ghcr.io authentication

**Decision**: Authenticate to `ghcr.io` using the automatically injected `GITHUB_TOKEN` (`secrets.GITHUB_TOKEN`). No additional secrets needed.

**Why**: For public repositories, `GITHUB_TOKEN` has write access to the same repo's GitHub Packages by default. Zero setup overhead.

**Alternatives considered**:
- Personal Access Token (PAT) stored as a secret — unnecessary for this case; PATs have broader scope and need rotation.

### D5 — `workflow_call` trigger on `ci.yml`

**Decision**: Add `workflow_call` as a trigger on `ci.yml` so `release.yml` can invoke it as a reusable job.

**Why**: Keeps the CI definition in one place. If the lint or test steps change, `release.yml` picks up the change automatically.

## Risks / Trade-offs

- **Service container startup latency** → postgres may not be ready when the test step starts. Mitigation: use `options: --health-cmd pg_isready` on the service definition; the job waits until healthy before proceeding.
- **`workflow_call` adds one level of indirection** → slightly harder to debug failures in `release.yml` if they originate inside `ci.yml`. Mitigation: acceptable trade-off given the duplication risk of the alternative.
- **Image pushed on every main merge** → `:latest` moves on every merge, which may surprise downstream consumers pinning to latest. Mitigation: document the tagging strategy; consumers should pin to SHAs or semver tags for stability.

## Migration Plan

1. Create `.github/workflows/ci.yml`.
2. Create `.github/workflows/release.yml`.
3. Push branch; open a PR to verify `ci.yml` triggers correctly.
4. Merge PR; verify `release.yml` builds and pushes image to `ghcr.io`.
5. Push a `v0.1.0` tag; verify semver tags appear on the package.

**Rollback**: Delete the workflow files. No application state is affected.

## Open Questions

None.
