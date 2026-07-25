## Context

The backend (`src/mobility_manager/presentation/api/app.py`) is a FastAPI app with no `docs_url`/`redoc_url`/`openapi_url` overrides, so `app.openapi()` and the default `/openapi.json` route already exist — nothing to add there. It also sets a global, restrictive `Content-Security-Policy: default-src 'none'` on every response (`add_security_headers` middleware) and cookie-based session auth (`session` cookie: `HttpOnly`, `Secure`, `SameSite=Strict`, set directly by the API in `auth.py`).

The frontend (`frontend/`, React 19 + Vite + react-router-dom v7) already proxies every backend call through a same-origin `/api/*` prefix:
- Production: `frontend/nginx.conf` — `location /api/ { proxy_pass http://api:8000/; }`.
- Dev: `frontend/vite.config.ts` — `server.proxy["/api"]` rewrites `/api` away and forwards to `http://localhost:8000`.

Every existing frontend API call (`frontend/src/api/*.ts`, e.g. `auth.ts`) already relies on this same-origin proxy plus `credentials: "include"` for cookie auth to work, with zero CORS/CSP considerations because the browser never sees a cross-origin request.

An earlier direction considered serving Swagger UI from the *backend* (self-hosted static assets, `fastapi.openapi.docs.get_swagger_ui_html`) but that would require: (a) carving an exception into the backend's strict CSP for the docs route, and (b) introducing a Node/npm build step into the currently Node-free Python Docker image to vendor `swagger-ui-dist` without committing it to the repo. Hosting the console in the frontend avoids both — the frontend already has its own Node/pnpm build pipeline (`Dockerfile.frontend`), and the docs page is just another same-origin page like the rest of the SPA.

## Goals / Non-Goals

**Goals:**
- Serve an interactive OpenAPI console (browse + "Try it out") from the frontend, reachable from a link on the main page, in every environment including production.
- Let "Try it out" work against protected endpoints using the browser's existing session cookie, with no manual token/Authorize-dialog step.
- Add zero new backend build complexity, CORS changes, or CSP exceptions.

**Non-Goals:**
- No ReDoc or any second, read-only doc viewer — Swagger UI's console is the only surface.
- No gating of the docs *page* itself behind login — it stays public; only the underlying endpoints keep their existing auth requirements.
- No new backend routes — `/openapi.json` already exists via FastAPI's default `app.openapi()`.
- No environment-based disabling of docs (e.g. prod-only toggle) — reachable everywhere, matching public-API norms (Stripe/GitHub-style).

## Decisions

**1. Host the console in the frontend, not the backend.**
The frontend already reverse-proxies `/api/*` to the backend at the exact same origin in both prod (nginx) and dev (Vite) — this is the same mechanism `frontend/src/api/auth.ts` already depends on for cookie auth. Putting the docs page here means the "Try it out" fetches are indistinguishable, from the browser's point of view, from any other authenticated call the SPA already makes: same origin, same cookie, no CORS preflight, no `allow_credentials` change, no SameSite issue. Alternative considered: self-hosted Swagger UI static assets served by FastAPI — rejected because it requires a CSP carve-out on the backend and a new Node build stage bolted onto an otherwise pure-Python Docker image.

**2. Use `swagger-ui-react`, fetch the spec at runtime, and inject `servers` client-side.**
FastAPI's generated `openapi.json` has no knowledge of the `/api` proxy prefix — its operation paths are `/vehicles/{id}`, not `/api/vehicles/{id}`, because that prefix is added by nginx/Vite, not by the app. The docs page therefore:
1. `fetch("/api/openapi.json")` to get the raw spec (same-origin, cookie not required — this endpoint is unauthenticated).
2. Parses the JSON and sets/overwrites `spec.servers = [{ url: "/api" }]` before handing the object to `<SwaggerUI spec={...} />` (not `url={...}` — using the pre-fetched, mutated object skips a second fetch and lets us mutate `servers` first).
3. Swagger UI then resolves every "Try it out" request against `/api` + the operation path, landing on the same proxy every other frontend call uses.

Alternative considered: a `requestInterceptor` prop on `SwaggerUI` that rewrites `req.url` to prepend `/api` on every outgoing request. Rejected in favor of `servers` injection per explicit instruction — injecting `servers` is also what actually drives the "Servers" dropdown Swagger UI renders in its own UI, so the displayed base URL matches reality instead of silently diverging from an intercepted one.

**3. `swagger-ui-react` as a frontend dependency; nothing committed beyond `package.json`/lockfile.**
Built by the existing `Dockerfile.frontend` (`pnpm install --frozen-lockfile && pnpm build`) — no new Docker stage, no vendored assets in the repo. Risk: `swagger-ui-react`'s peer dependency range historically targets React 16–18; this repo is on React 19.2. This must be verified during implementation (`pnpm add swagger-ui-react` and confirm no peer-dependency conflict or runtime warning). If it doesn't support React 19 cleanly, fall back to the plain `swagger-ui` package (vanilla JS/dist bundle, no React peer dependency) mounted into a ref via a small wrapper component (`useEffect` + `SwaggerUIBundle({...}, domNode)`), which sidesteps the React-version coupling entirely at the cost of a slightly less idiomatic React wrapper.

**4. Docs page is public, in every environment, with no visibility toggle.**
Matches user's explicit decision. The schema itself isn't secret (route shapes are visible to anyone reading the frontend bundle's network calls anyway), and protected endpoints remain protected by their own `get_current_user` dependency regardless of who can view the console.

**5. Link placement: `Nav.tsx`, unconditional (not inside the `user ? ... : ...` branch).**
Mirrors the existing `nav.map` link, which is also always visible regardless of auth state — consistent with "docs page is public."

## Risks / Trade-offs

- **[Risk]** `swagger-ui-react` may not officially support React 19 → **Mitigation**: verify at implementation time; fall back to the vanilla `swagger-ui` dist bundle in a thin wrapper component if peer-dependency issues surface (see Decision 3).
- **[Risk]** `servers` injection is a runtime mutation of the fetched spec object; if `swagger-ui-react` is ever swapped for `url`-based loading instead of `spec`-based, this step would need to move server-side or into a interceptor → **Mitigation**: keep the injection isolated in one small function (e.g. `injectApiServer(spec)`) so the seam is obvious and easy to relocate.
- **[Risk]** A public, unauthenticated `/api-docs` page makes every route's shape (including internal-only-feeling ones) trivially discoverable → **Mitigation**: accepted per explicit user decision; no route in this API relies on obscurity for its security, all protected routes enforce `get_current_user`/ownership checks independent of who can see the schema.
- **[Trade-off]** No ReDoc means no clean read-only/print-friendly view of the API — acceptable per explicit user decision ("one is enough").

## Migration Plan

No data migration. Purely additive frontend change:
1. Add `swagger-ui-react` dependency, verify build.
2. Add the docs route/page and the `injectApiServer` helper.
3. Add the Nav link.
4. Deploy via the existing frontend pipeline — no backend deploy, no env var, no Docker changes needed.
Rollback: revert the frontend change; nothing on the backend or database is touched.

## Open Questions

- Exact path for the new route (`/api-docs` used as a placeholder throughout — confirm before or during tasks if a different path is preferred).
