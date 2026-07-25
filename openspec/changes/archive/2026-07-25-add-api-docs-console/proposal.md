## Why

The API has no interactive documentation. Consumers (and the maintainer) have no way to browse available endpoints, request/response shapes, or try a call without reading source code or reaching for a separate HTTP client. FastAPI already generates an OpenAPI schema from the existing routes, but no UI is exposed to browse or exercise it, and no route currently serves `openapi.json` for external consumption.

## What Changes

- Add a `GET /openapi.json`-equivalent fetch in the frontend that reads FastAPI's already-generated OpenAPI schema through the existing same-origin `/api` proxy (nginx in production, Vite in dev) — no new backend route needed, since `app.openapi()` is already exposed by default.
- Add a new frontend route (e.g. `/api-docs`) that renders `swagger-ui-react`, fetches the spec via `/api/openapi.json`, injects `servers: [{ url: "/api" }]` into the fetched spec object before handing it to the `SwaggerUI` component (so "Try it out" requests resolve through the same `/api` prefix the rest of the app already uses), and renders the interactive console.
- Add a visible link from the app's main/landing page to the new docs route (e.g. "API Docs").
- `swagger-ui-react` (and its type declarations) added as a frontend dependency, built by the existing `Dockerfile.frontend` / `pnpm build` pipeline — no new dependency or build stage added to the Python backend image.
- No ReDoc — Swagger UI's interactive console is the only viewer; read-only browsing isn't a separate requirement.
- No backend CSP, CORS, or `allow_credentials` changes — the docs page and all "Try it out" calls are same-origin (proxied through `/api`), exactly like every other frontend API call already in `frontend/src/api/*.ts`. Session cookie auth continues to work automatically for logged-in users testing protected endpoints, with no Authorize-dialog wiring needed.
- Docs page is public (reachable without login) in every environment, including production; protected endpoints still 401 through the console unless the browser already holds a valid session cookie for this origin.

## Capabilities

### New Capabilities
- `api-docs-console`: Interactive OpenAPI documentation and request console, served from the frontend, backed by the API's existing auto-generated OpenAPI schema.

### Modified Capabilities
_None — no existing capability's requirements change; this only adds a new frontend-facing capability._

## Impact

- **Affected code**: `frontend/` — new route/page component, new `swagger-ui-react` dependency, a link added to the landing/main page. No backend code changes (FastAPI's default `openapi.json`/`app.openapi()` is used as-is).
- **Dependencies**: `swagger-ui-react` (+ `@types/swagger-ui-react` if used with TypeScript) added to `frontend/package.json`.
- **Systems**: None — no new backend build stage, no CORS/CSP/Docker changes. Relies entirely on the existing nginx (`/api/` proxy_pass) and Vite dev-server (`/api` rewrite) same-origin proxying already in place.
