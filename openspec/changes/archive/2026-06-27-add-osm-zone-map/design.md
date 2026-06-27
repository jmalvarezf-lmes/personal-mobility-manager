## Context

The backend stores Madrid SER zones (street name, zone type, spot count, UTM/WGS84 coordinates) ingested from the city's open data CSV. The FastAPI app exposes a single `GET /parking/ser-zone` endpoint that returns the nearest zone to a given coordinate. There is no frontend and no bulk data export.

The goal is to add a browser map that renders all stored zones as coloured markers over a self-hosted OpenStreetMap tile server, without touching any existing functionality.

## Goals / Non-Goals

**Goals:**
- Add `colour` to the domain layer so zone type carries its visual meaning
- Add `GET /parking/ser-zones` to export all zones for map rendering
- Add `GET /config` to expose runtime config (tile URL) to the frontend
- Scaffold a React SPA in `frontend/` with a single map page
- Render zones as coloured circle markers with tooltips (street, type, spots)
- Make the OSM tile server URL runtime-configurable via `OSM_TILE_URL` env var

**Non-Goals:**
- Authentication or user accounts (future change)
- Per-city routing or multi-city selector (future)
- Filtering, search, or clustering of map markers (future)
- Mobile-optimised layout (acceptable but not required)
- Real-time zone updates (scheduler already refreshes; page reload is enough)

## Decisions

### D1 — Colour lives in the domain layer

`ZoneType` base class gets an abstract `colour` property returning a hex string. `MadridZoneType` implements it:

```
Azul          → #2563EB  (blue-600)
Verde         → #16A34A  (green-600)
AltaRotacion  → #6B7280  (grey-500)
Naranja       → #6B7280  (grey-500, no standard SER colour)
Rojo          → #6B7280  (grey-500, no standard SER colour)
```

**Why**: The colour is part of the zone type's meaning, not a display concern. Keeping it in the domain ensures it is consistent across any future presentation layer (map, PDF, notification text, etc.). Alternatives considered: frontend lookup table (colour scattered and duplicated), API schema field (would need to be kept in sync with domain logic).

### D2 — Zones bulk endpoint returns a flat JSON list

`GET /parking/ser-zones?city=madrid` returns:
```json
{
  "city": "madrid",
  "zones": [
    {
      "street_name": "...",
      "zone_type": "Azul",
      "colour": "#2563EB",
      "spot_count": 12,
      "lat": 40.4168,
      "lng": -3.7038
    }
  ]
}
```

No pagination for now — Madrid's current dataset is ~10k records, all fitting comfortably in a single JSON response (~2 MB). If datasets grow significantly this decision should be revisited.

**Why flat list over GeoJSON**: react-leaflet works with plain JS objects just as well as GeoJSON, and a flat list is simpler to consume and test. GeoJSON can be introduced later if third-party tools need to consume the endpoint.

### D3 — Frontend fetches tile URL from `/config` at startup

`GET /config` returns:
```json
{ "osm_tile_url": "http://192.168.1.x:8080/tile/{z}/{x}/{y}.png" }
```

**Why runtime not build-time**: The tile server lives on a home LAN. The URL can change (different port, different host). A build-time env var (Vite's `VITE_` prefix) would require rebuilding the React app each time. Runtime fetch keeps the frontend artifact portable.

### D4 — React SPA with Vite + TypeScript + react-leaflet + Tailwind CSS, managed with pnpm

Stack:
- **React 19** — component model for future pages
- **Vite** — fast dev server and build
- **TypeScript** — type safety, IDE support
- **react-leaflet 4** — first-class React bindings for Leaflet; OSM tile support is native
- **Tailwind CSS** — utility-first, no CSS files needed
- **shadcn/ui** — accessible UI primitives for the future (installed now, used later)
- **pnpm** — package manager; faster installs and strict dependency isolation vs npm; `pnpm-lock.yaml` committed for reproducibility

Frontend lives in `frontend/` at project root. It is a standalone pnpm project. In development it runs on port 5173 and proxies `/api` calls to FastAPI on port 8000 via Vite's built-in proxy (avoids CORS issues in dev). In production the built `dist/` is served by the `frontend` docker-compose service via nginx.

**Alternatives considered**: HTMX + Jinja2 (keeps Python-only, but auth forms and reactive state are awkward); plain Leaflet HTML (no component model, hard to grow); Vue 3 (same capability as React, weaker ecosystem for future help); npm (chosen pnpm for speed and stricter hoisting).

### D5 — Playwright for end-to-end tests

Playwright is installed as a dev dependency in `frontend/` (`pnpm add -D @playwright/test`). Tests live in `frontend/e2e/` and run against the full stack (backend + postgres + frontend). The test suite covers:
- Map page loads without JS errors
- At least one zone marker is visible on the canvas after data loads
- Hovering a marker shows a tooltip with street name, zone type, and spot count

Playwright is chosen over Cypress because it supports multiple browsers out of the box, has a better async model, and is faster in CI. Tests run with `pnpm exec playwright test` and are independent of the Vite dev server (they target the built/served app or the dev server via `baseURL`).

**Why e2e tests for a map**: Unit tests cannot verify that react-leaflet actually renders markers to the DOM/canvas correctly. Playwright can assert on DOM elements (tooltips, container presence) and is the right tool for this layer.

### D6 — docker-compose runs the full stack

`docker-compose.yml` gains a `frontend` service using a multi-stage `Dockerfile.frontend`:

```
Stage 1 (build):  node:22-alpine + pnpm → pnpm install + pnpm build → dist/
Stage 2 (serve):  nginx:alpine → copy dist/ → serve on :80
```

The `frontend` service depends on `app` (FastAPI). The nginx config proxies `/api/` to the `app` service so the same `/api` prefix convention works in production as in Vite dev proxy.

Port mapping: `frontend` exposes `:3000` on the host (avoids collision with the FastAPI port 8000).

**Why nginx not `pnpm preview`**: nginx is more stable for home-server production use; `pnpm preview` is Vite's dev-mode preview server, not intended for production. The multi-stage build also keeps the final image small (~25 MB vs ~300 MB with Node).

### D7 — No new auth for this change

The zones endpoint and config endpoint are public (no auth token required) for this change. Auth is a separate future change. CORS is already configured; the frontend origin (`http://localhost:5173` in dev) will be added to `CORS_ORIGINS`. In docker-compose production mode the frontend nginx proxies requests directly to the `app` service, so CORS is not required for that path.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Self-hosted OSM tile server is down | Frontend shows an empty grey tile layer; zones still render. No error handling required beyond what Leaflet provides by default. |
| 10k zone markers causes browser performance issues | Use Leaflet's `CircleMarker` (canvas-rendered) instead of `Marker` (DOM node per pin); Leaflet handles canvas-based rendering efficiently up to ~50k points. |
| `colour` property on ZoneType breaks existing MadridZoneType subclass if not implemented | Add a default fallback `#6B7280` in the base `ZoneType.colour` so existing city providers without implementation don't crash. |
| Frontend build step unfamiliar to maintainer | Vite defaults are zero-config; `pnpm dev` and `pnpm build` are the only commands needed day-to-day. pnpm is installed with `npm install -g pnpm` once. |
| Playwright tests flaky on CI (map canvas timing) | Use `waitForSelector` on tooltip elements rather than canvas pixels; Playwright's auto-retry makes this reliable. |

## Migration Plan

1. Deploy backend with new `/parking/ser-zones` and `/config` endpoints (no breaking changes to existing endpoints)
2. Add `OSM_TILE_URL` to `.env` / `docker-compose.yml`
3. Run `docker-compose up --build` — builds and starts backend, postgres, and frontend in one step

Rollback: remove the static files mount and the two new routers — no DB migrations involved.

## Open Questions

- Should `GET /parking/ser-zones` support a bounding-box filter (`?bbox=lat1,lng1,lat2,lng2`) now, or is full-list sufficient? **Decision for now: full list; bbox is a future optimisation.**
- Production serving: FastAPI `StaticFiles` mount or nginx? **Leave to the implementer — both work; nginx is preferred for production but optional for home infra.**
