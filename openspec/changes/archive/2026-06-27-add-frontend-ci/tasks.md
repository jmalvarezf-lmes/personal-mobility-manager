## 1. Frontend ESLint Setup

- [x] 1.1 Add ESLint devDependencies to `frontend/package.json`: `eslint`, `@eslint/js`, `typescript-eslint`, `eslint-plugin-react-hooks`
- [x] 1.2 Create `frontend/eslint.config.js` with flat config using `@typescript-eslint/recommended` and `react-hooks/recommended`
- [x] 1.3 Add `lint` script to `frontend/package.json`: `eslint src/`
- [x] 1.4 Add `type-check` script to `frontend/package.json`: `tsc --noEmit`
- [x] 1.5 Run `pnpm lint` and `pnpm type-check` locally and verify both exit 0

## 2. Playwright CI Setup

- [x] 2.1 Add `webServer` block to `frontend/playwright.config.ts`: command `pnpm dev`, url `http://localhost:5173`, timeout 30000ms, `reuseExistingServer: !process.env.CI`

## 3. Update CI Workflow

- [x] 3.1 Rename `lint` job to `lint-backend` in `.github/workflows/ci.yml`
- [x] 3.2 Rename `test` job to `test-backend` in `.github/workflows/ci.yml`
- [x] 3.3 Add `lint-frontend` job to `.github/workflows/ci.yml`: install pnpm via `pnpm/action-setup@v4`, checkout, install deps (`pnpm install --frozen-lockfile` in `frontend/`), run `pnpm type-check` then `pnpm lint`
- [x] 3.4 Add `test-frontend` job to `.github/workflows/ci.yml`: install pnpm, checkout, install deps, install Chromium (`pnpm exec playwright install --with-deps chromium`), run `pnpm exec playwright test` — all steps with `working-directory: frontend`

## 4. Update Release Workflow

- [x] 4.1 Rename `docker` job to `docker-backend` in `.github/workflows/release.yml`
- [x] 4.2 Update image name in the `docker-backend` job metadata step from `ghcr.io/jmalvarezf-lmes/personal-mobility-manager` to `ghcr.io/jmalvarezf-lmes/personal-mobility-manager-backend`
- [x] 4.3 Add `docker-frontend` job to `.github/workflows/release.yml` with `needs: ci`, building from `Dockerfile.frontend` and pushing to `ghcr.io/jmalvarezf-lmes/personal-mobility-manager-frontend` with the same tag strategy as the backend
