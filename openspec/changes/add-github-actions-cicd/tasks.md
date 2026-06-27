## 1. Scaffold

- [x] 1.1 Create `.github/workflows/` directory at the project root

## 2. CI workflow

- [x] 2.1 Create `.github/workflows/ci.yml` with triggers `pull_request` and `workflow_call`
- [x] 2.2 Add `lint` job: checkout, set up Python 3.12, `pip install -r requirements-dev.txt && pip install -e .`, run `ruff check src/ tests/`, run `mypy src/`
- [x] 2.3 Add `test` job: declare `postgres:16-alpine` service with health-check (`pg_isready --username test --dbname testdb`), set `POSTGRES_DSN` env var pointing to the service container
- [x] 2.4 In the `test` job: checkout, set up Python 3.12, install deps (`requirements-dev.txt` + `-e .`), run `alembic upgrade head`, run `pytest tests/ --cov=mobility_manager --cov-report=term-missing`

## 3. Release workflow

- [x] 3.1 Create `.github/workflows/release.yml` with triggers `push` on branch `main`, tags `v*.*.*`, and `workflow_dispatch`
- [x] 3.2 Add `ci` job that calls `.github/workflows/ci.yml` via `uses: ./.github/workflows/ci.yml`
- [x] 3.3 Add `docker` job with `needs: ci`; add step to log in to `ghcr.io` using `docker/login-action` with `registry: ghcr.io`, `username: ${{ github.actor }}`, `password: ${{ secrets.GITHUB_TOKEN }}`
- [x] 3.4 Add `docker/metadata-action` step to compute tags: flavor `latest=true`; tags pattern `type=semver,pattern={{version}}`, `type=semver,pattern={{major}}.{{minor}}`, `type=semver,pattern={{major}}`, `type=sha` (for non-tag pushes)
- [x] 3.5 Add `docker/build-push-action` step: `push: true`, `tags` and `labels` from metadata-action outputs, `context: .`

## 4. Verify

- [ ] 4.1 Push this branch and open a PR; confirm the `ci.yml` workflow triggers and both `lint` and `test` jobs pass (including integration tests against the postgres service)
- [ ] 4.2 Merge the PR to `main`; confirm `release.yml` triggers, CI passes, and an image is pushed to `ghcr.io` with `:latest` and `:<sha>` tags
- [ ] 4.3 Push a `v0.1.0` tag; confirm the image is pushed with tags `:0.1.0`, `:0.1`, `:0`, and `:latest`
- [ ] 4.4 Confirm the GitHub Package is public (`docker pull ghcr.io/jmalvarezf-lmes/personal-mobility-manager:latest` without credentials)
