## 1. Dependency setup

- [x] 1.1 Add `swagger-ui-react` (and `@types/swagger-ui-react` if no bundled types) to `frontend/package.json` via `pnpm add`.
- [x] 1.2 Run `pnpm build` and confirm no peer-dependency error/warning against React 19. If `swagger-ui-react` is incompatible, remove it and instead add the plain `swagger-ui` package, to be wired manually via `SwaggerUIBundle` in a `useEffect` (see design.md Decision 3 fallback) — adjust tasks 2.x accordingly if this path is taken.

## 2. Docs page implementation

- [x] 2.1 Create `frontend/src/api/openapi.ts` (or similar) exporting an `injectApiServer(spec: Record<string, unknown>)` helper that sets `spec.servers = [{ url: "/api" }]` and returns the mutated spec.
- [x] 2.2 Create `frontend/src/pages/ApiDocsPage.tsx`: on mount, `fetch("/api/openapi.json")`, parse JSON, pass through `injectApiServer`, and render `<SwaggerUI spec={spec} />` (loading/error states while the fetch is in flight).
- [x] 2.3 Add translation keys for the page (e.g. `page.apiDocs.title`) to `frontend/public/locales/en/translation.json` and `frontend/public/locales/es/translation.json`, following the existing key structure used by other pages (see `page.landing.title` in `LandingPage.tsx`).

## 3. Routing and navigation

- [x] 3.1 Add a `/api-docs` route in `frontend/src/App.tsx` rendering `ApiDocsPage`, outside `ProtectedRoute` (public page per design.md Decision 4).
- [x] 3.2 Add an unconditional link to `/api-docs` in `frontend/src/components/Nav.tsx`, alongside the existing `nav.map` link (outside the `user ? ... : ...` branch), with a matching `nav.apiDocs` translation key added to both locale files.

## 4. Tests

- [x] 4.1 Add `frontend/src/pages/ApiDocsPage.test.tsx` (Vitest + Testing Library, matching the pattern in `PreferencesPage.test.tsx`): mock `fetch` to return a minimal OpenAPI document, assert the page renders without crashing and that `injectApiServer`'s effect is observable (e.g. the fetched spec object passed to `SwaggerUI` includes the injected `servers` entry).
- [x] 4.2 Add a unit test for `injectApiServer` covering: spec with no existing `servers` key, and spec with a pre-existing `servers` key (confirm it's overwritten, not appended).
- [x] 4.3 Add/extend a Nav test asserting the API docs link renders and is visible with no authenticated user (public visibility requirement).

## 5. Manual verification

- [x] 5.1 Run the app via `docker compose up` (or `make api` + `pnpm dev`), open `/api-docs`, and confirm the schema renders and lists all routers (auth, vehicles, parking, zones, etc.). — verified by user.
- [x] 5.2 Log in through the real Google OAuth flow in the same browser, return to `/api-docs`, and confirm a protected "Try it out" call (e.g. `GET /vehicles`) succeeds using the existing session cookie with no extra Authorize step. — verified by user.
- [x] 5.3 Without logging in, confirm the same protected "Try it out" call returns 401. — verified by user.
- [x] 5.4 Confirm `make test` (frontend + backend) still passes; no backend files should have changed as part of this work.
