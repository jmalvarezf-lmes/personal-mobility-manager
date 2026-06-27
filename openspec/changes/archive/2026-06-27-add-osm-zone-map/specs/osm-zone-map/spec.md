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

### Requirement: Zone markers are rendered with their canonical colour
The map page SHALL fetch all zones from `GET /parking/ser-zones?city=madrid` and render each as a filled `CircleMarker` using the zone's `colour` field as the fill and stroke colour.

#### Scenario: Blue zone renders as blue marker
- **WHEN** a zone with `zone_type: "Azul"` and `colour: "#2563EB"` is in the response
- **THEN** a circle marker with fill colour `#2563EB` is rendered at the zone's coordinates

#### Scenario: Grey marker for unknown zone type
- **WHEN** a zone with `colour: "#6B7280"` is in the response
- **THEN** a circle marker with fill colour `#6B7280` is rendered at the zone's coordinates

### Requirement: Zone markers have tooltips showing street, type, and spots
Each circle marker SHALL display a Leaflet tooltip on hover containing the zone's `street_name`, `zone_type`, and `spot_count`.

#### Scenario: Tooltip shows correct zone details
- **WHEN** the user hovers over a zone marker
- **THEN** a tooltip is displayed containing the street name, zone type label, and spot count for that zone

### Requirement: Dev proxy forwards API calls to FastAPI
The Vite development configuration SHALL proxy requests from `frontend/` to the path prefix `/api` to `http://localhost:8000` so that the frontend can call FastAPI endpoints without CORS issues during development.

#### Scenario: API calls reach FastAPI in dev
- **WHEN** the frontend calls `/api/parking/ser-zones?city=madrid` during development
- **THEN** the request is forwarded to `http://localhost:8000/parking/ser-zones?city=madrid`

### Requirement: Playwright e2e tests cover the map page
The `frontend/` project SHALL include Playwright end-to-end tests in `frontend/e2e/`. Running `pnpm exec playwright test` SHALL execute the suite. Tests SHALL run against a live stack (backend + postgres reachable). The suite SHALL cover: map container present, at least one zone marker rendered, and tooltip content visible on interaction.

#### Scenario: Map container is present on load
- **WHEN** Playwright navigates to the map page
- **THEN** an element with the Leaflet map container class is present in the DOM

#### Scenario: Zone markers appear after data loads
- **WHEN** Playwright navigates to the map page and waits for the zones API response
- **THEN** at least one SVG or canvas element representing a zone marker is present

#### Scenario: Tooltip shows zone details on marker interaction
- **WHEN** Playwright clicks or hovers over a visible zone marker
- **THEN** a tooltip element is visible containing a street name, a zone type string, and a spot count number

### Requirement: Full stack starts with docker-compose up
A `frontend` service SHALL be added to `docker-compose.yml` using a multi-stage build (`Dockerfile.frontend`): stage 1 installs dependencies with pnpm and runs `pnpm build`; stage 2 serves `dist/` via nginx on port 80. The service SHALL be exposed on host port 3000. Running `docker-compose up --build` SHALL start backend, postgres, and frontend together with no additional steps required.

#### Scenario: docker-compose up starts the frontend
- **WHEN** `docker-compose up --build` is executed from the project root
- **THEN** the frontend is accessible at `http://localhost:3000` and the map page loads

#### Scenario: nginx proxies API calls to the backend service
- **WHEN** the browser (served by the `frontend` container) calls `/api/parking/ser-zones?city=madrid`
- **THEN** nginx forwards the request to the `app` service and returns zone data
