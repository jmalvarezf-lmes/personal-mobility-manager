## ADDED Requirements

### Requirement: React SPA scaffold exists in frontend/ and is managed with pnpm
A `frontend/` directory SHALL exist at the project root containing a Vite + React + TypeScript project managed with pnpm. Running `pnpm install && pnpm dev` inside `frontend/` SHALL start a development server on port 5173. Running `pnpm build` SHALL produce a static bundle in `frontend/dist/`. A `pnpm-lock.yaml` file SHALL be committed to version control for reproducible installs.

#### Scenario: Dev server starts with pnpm
- **WHEN** `pnpm dev` is executed inside `frontend/`
- **THEN** Vite starts without errors and the app is accessible at `http://localhost:5173`

#### Scenario: Production build succeeds with pnpm
- **WHEN** `pnpm build` is executed inside `frontend/`
- **THEN** `frontend/dist/index.html` and associated assets are generated without errors

### Requirement: Map page renders OSM tiles
The map page SHALL fetch the tile URL from `GET /config` on the backend and use it as the Leaflet tile layer source. If `osm_tile_url` is null or the fetch fails, the map SHALL fall back to the public OpenStreetMap tile URL (`https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`).

#### Scenario: Self-hosted tile URL is used when configured
- **WHEN** the backend returns a non-null `osm_tile_url`
- **THEN** the Leaflet map uses that URL as its tile layer

#### Scenario: Fallback tile URL when config is absent
- **WHEN** the backend returns `{ "osm_tile_url": null }` or the `/config` request fails
- **THEN** the Leaflet map uses `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`

### Requirement: Zone boundaries are rendered as polygons with their canonical colour
The map page SHALL fetch all zones from `GET /parking/ser-zones?city=madrid` and render each as a filled polygon shape (via `react-leaflet`'s `GeoJSON`/`Polygon`) using the zone's `colour` field as the fill and stroke colour.

#### Scenario: Blue zone renders as blue polygon
- **WHEN** a zone with `zone_type: "Azul"` and `colour: "#2563EB"` is in the response
- **THEN** a polygon with fill colour `#2563EB` is rendered using the zone's `geometry`

#### Scenario: Grey polygon for unknown zone type
- **WHEN** a zone with `colour: "#6B7280"` is in the response
- **THEN** a polygon with fill colour `#6B7280` is rendered using the zone's `geometry`

#### Scenario: Multi-part zone renders as multiple polygon pieces
- **WHEN** a zone's `geometry` is a GeoJSON `MultiPolygon`
- **THEN** all constituent polygon parts are rendered as one visually grouped shape sharing the same colour and tooltip

### Requirement: Zone polygons have tooltips showing zone number, district, and spots
Each zone polygon SHALL display a Leaflet tooltip on hover containing the zone's `zone_number`, `district`, and `spot_count`. Street names SHALL NOT be shown in the tooltip — the bulk zones response this page consumes does not include them (see `zones-bulk-query`), and fetching them per-hover would require an extra network call per interaction.

#### Scenario: Tooltip shows correct zone details
- **WHEN** the user hovers over a zone polygon
- **THEN** a tooltip is displayed containing the zone number, district, and spot count for that zone, with no street names and no additional network request

### Requirement: Zone frontiers are rendered as a pale neutral layer beneath the precise zone polygons
The map page SHALL fetch the `frontiers` array from `GET /parking/ser-zones?city=madrid` and render each as a filled polygon shape using a single fixed pale grey style (not derived from any zone's `colour`), drawn beneath the existing precise per-`(zone_number, zone_type)` polygons so both are visible at once.

#### Scenario: Frontier renders in neutral grey regardless of the zone_number's colours
- **WHEN** a zone_number with both Azul and Verde precise zones is rendered
- **THEN** its single frontier entry renders in the same fixed pale grey used for every other frontier, not a colour derived from either zone_type

#### Scenario: Frontier renders beneath precise zone polygons
- **WHEN** both a frontier and its zone_number's precise zone polygons are visible in the same viewport
- **THEN** the precise, fully-coloured polygons render on top of the pale grey frontier, not the other way around

#### Scenario: Frontier tooltip shows the neighbourhood name
- **WHEN** the user hovers over a frontier polygon (in an area not covered by a precise zone polygon)
- **THEN** a tooltip is displayed containing the zone number and neighbourhood name

### Requirement: Dev proxy forwards API calls to FastAPI
The Vite development configuration SHALL proxy requests from `frontend/` to the path prefix `/api` to `http://localhost:8000` so that the frontend can call FastAPI endpoints without CORS issues during development.

#### Scenario: API calls reach FastAPI in dev
- **WHEN** the frontend calls `/api/parking/ser-zones?city=madrid` during development
- **THEN** the request is forwarded to `http://localhost:8000/parking/ser-zones?city=madrid`

### Requirement: Playwright e2e tests cover the map page
The `frontend/` project SHALL include Playwright end-to-end tests in `frontend/e2e/`. Running `pnpm exec playwright test` SHALL execute the suite. Tests SHALL run against a live stack (backend + postgres reachable). The suite SHALL cover: map container present, at least one zone polygon rendered, and tooltip content visible on interaction.

#### Scenario: Map container is present on load
- **WHEN** Playwright navigates to the map page
- **THEN** an element with the Leaflet map container class is present in the DOM

#### Scenario: Zone polygons appear after data loads
- **WHEN** Playwright navigates to the map page and waits for the zones API response
- **THEN** at least one SVG path element representing a zone polygon is present

#### Scenario: Tooltip shows zone details on polygon interaction
- **WHEN** Playwright clicks or hovers over a visible zone polygon
- **THEN** a tooltip element is visible containing a zone number, a district name, and a spot count number

#### Scenario: Frontier polygons appear after data loads
- **WHEN** Playwright navigates to the map page and waits for the zones API response
- **THEN** at least one frontier polygon element is present, in addition to the existing precise zone polygon assertions

### Requirement: Full stack starts with docker-compose up
A `frontend` service SHALL be added to `docker-compose.yml` using a multi-stage build (`Dockerfile.frontend`): stage 1 installs dependencies with pnpm and runs `pnpm build`; stage 2 serves `dist/` via nginx on port 80. The service SHALL be exposed on host port 3000. Running `docker-compose up --build` SHALL start backend, postgres, and frontend together with no additional steps required.

#### Scenario: docker-compose up starts the frontend
- **WHEN** `docker-compose up --build` is executed from the project root
- **THEN** the frontend is accessible at `http://localhost:3000` and the map page loads

#### Scenario: nginx proxies API calls to the backend service
- **WHEN** the browser (served by the `frontend` container) calls `/api/parking/ser-zones?city=madrid`
- **THEN** nginx forwards the request to the `app` service and returns zone data
