## 1. Domain — Zone Colour

- [x] 1.1 Add `colour` property to `ZoneType` base class in `domain/value_objects/zone_type.py` returning `"#6B7280"` as the default
- [x] 1.2 Override `colour` in `MadridZoneType` in `infrastructure/parking_services/madrid/zone_type.py`: Azul → `#2563EB`, Verde → `#16A34A`, others → `#6B7280`
- [x] 1.3 Add unit tests for `ZoneType.colour` base fallback and all five `MadridZoneType` variants

## 2. Backend — Config Endpoint

- [x] 2.1 Add `get_osm_tile_url()` to `config.py` reading `OSM_TILE_URL` env var, returning `None` if unset
- [x] 2.2 Create router `presentation/api/routers/config.py` with `GET /config` returning `{ "osm_tile_url": str | None }`
- [x] 2.3 Register the config router in `presentation/api/app.py`
- [x] 2.4 Add `OSM_TILE_URL` to `.env.example` (or document it alongside existing env vars)
- [x] 2.5 Add unit test for `GET /config` — with and without `OSM_TILE_URL` set

## 3. Backend — Bulk Zones Endpoint

- [x] 3.1 Add `list_all` method to `SerZoneRepository` port (`domain/ports/ser_zone_repository.py`) returning a list of all `SerZone` entities
- [x] 3.2 Implement `list_all` in `infrastructure/repositories/postgres/ser_zone_repo.py` querying all rows
- [x] 3.3 Add `ListSerZonesResponse` and `SerZoneMapItem` schemas to `presentation/api/schemas.py` (fields: street_name, zone_type, colour, spot_count, lat, lng)
- [x] 3.4 Create router `presentation/api/routers/zones.py` with `GET /parking/ser-zones?city=madrid` — calls `list_all`, maps entities to schema (resolving colour from entity zone type), returns 404 for unknown city
- [x] 3.5 Register the zones router in `presentation/api/app.py`
- [x] 3.6 Add integration test for `GET /parking/ser-zones?city=madrid` (empty list case and populated case)
- [x] 3.7 Add unit test for unknown city returning 404

## 4. Frontend — Scaffold

- [x] 4.1 Initialise React + Vite + TypeScript project: run `pnpm create vite@latest frontend -- --template react-ts` from project root
- [x] 4.2 Install runtime dependencies inside `frontend/`: `pnpm add react-leaflet leaflet @types/leaflet`
- [x] 4.3 Install Tailwind: `pnpm add -D tailwindcss @tailwindcss/vite`; add plugin to `vite.config.ts`; add `@import "tailwindcss"` to `frontend/src/index.css`
- [x] 4.4 Configure Vite dev proxy in `frontend/vite.config.ts`: `/api` → `http://localhost:8000`
- [x] 4.5 Remove Vite boilerplate (default `App.tsx` content, `assets/react.svg`, `public/vite.svg`)
- [x] 4.6 Verify `pnpm-lock.yaml` is committed and `frontend/node_modules` is excluded by `.gitignore`

## 5. Frontend — Map Page

- [x] 5.1 Create `frontend/src/types/zone.ts` with a `Zone` interface matching the API response shape
- [x] 5.2 Create `frontend/src/api/config.ts` — fetch `GET /api/config`, return `osm_tile_url` or null
- [x] 5.3 Create `frontend/src/api/zones.ts` — fetch `GET /api/parking/ser-zones?city=madrid`, return `Zone[]`
- [x] 5.4 Create `frontend/src/components/ZoneMap.tsx` — a `MapContainer` with a `TileLayer` (URL from config, fallback to public OSM), and a `CircleMarker` per zone using `colour` for fill and stroke, with a `Tooltip` showing street name, zone type, and spot count
- [x] 5.5 Create `frontend/src/pages/MapPage.tsx` — calls both API hooks, shows a loading state while fetching, renders `ZoneMap` with the fetched zones
- [x] 5.6 Wire `MapPage` as the root route in `frontend/src/App.tsx`
- [x] 5.7 Set initial map center to Madrid (40.4168, -3.7038) and zoom level 13

## 6. Playwright — E2E Tests

- [x] 6.1 Install Playwright: `pnpm add -D @playwright/test` inside `frontend/`; run `pnpm exec playwright install --with-deps chromium` to install the browser binary
- [x] 6.2 Add `playwright.config.ts` in `frontend/` with `baseURL: 'http://localhost:5173'` and a single `chromium` project
- [x] 6.3 Create `frontend/e2e/map.spec.ts` — test: map container present on load (assert Leaflet container element exists)
- [x] 6.4 Add test in `frontend/e2e/map.spec.ts` — zones loaded: wait for `/api/parking/ser-zones` response, assert at least one marker element is present in the DOM
- [x] 6.5 Add test in `frontend/e2e/map.spec.ts` — tooltip: interact with a marker, assert tooltip element contains street name, zone type, and a numeric spot count
- [ ] 6.6 Verify `pnpm exec playwright test` passes with the dev stack running (`pnpm dev` + backend)

## 7. Docker Compose — Frontend Service

- [x] 7.1 Create `Dockerfile.frontend` at project root — stage 1: `node:22-alpine`, install pnpm, copy `frontend/`, run `pnpm install --frozen-lockfile && pnpm build`; stage 2: `nginx:alpine`, copy `dist/` to nginx html dir
- [x] 7.2 Create `frontend/nginx.conf` — serve static files from `/usr/share/nginx/html`; proxy `/api/` to `http://app:8000/`
- [x] 7.3 Add `frontend` service to `docker-compose.yml`: build from `Dockerfile.frontend`, expose port `3000:80`, depends_on `app`
- [x] 7.4 Add `OSM_TILE_URL` to the `app` service environment block in `docker-compose.yml` (empty string default)
- [ ] 7.5 Run `docker-compose up --build` and confirm frontend is reachable at `http://localhost:3000` with zone markers visible

## 8. Verification

- [x] 8.1 Run backend tests: `pytest tests/ -x` — all pass
- [x] 8.2 Run mypy: `mypy src/` — no new errors
- [x] 8.3 Run ruff: `ruff check src/ tests/` — no new errors
- [ ] 8.4 Start dev stack (`pnpm dev` + backend); confirm map loads at `http://localhost:5173` with zone markers visible
- [ ] 8.5 Confirm markers are blue for Azul zones, green for Verde zones, grey for Alta Rotación zones (verify via tooltip)
- [ ] 8.6 Set `OSM_TILE_URL` env var and confirm the tile layer switches to the configured URL
- [ ] 8.7 Run `pnpm exec playwright test` — all e2e tests pass
- [ ] 8.8 Run `docker-compose up --build` — full stack starts, map accessible at `http://localhost:3000`
