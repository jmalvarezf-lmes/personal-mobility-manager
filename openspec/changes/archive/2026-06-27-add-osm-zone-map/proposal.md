## Why

The backend ingests and stores Madrid SER parking zones with zone types and coordinates, but there is no visual interface to see where those zones are on a map. Adding an OpenStreetMap-based web view makes the data immediately useful and lays the foundation for the project's web frontend.

## What Changes

- Add a `colour` property to the `ZoneType` domain base class and implement it in `MadridZoneType` (Azul → blue, Verde → green, all others → grey)
- Add a new API endpoint `GET /parking/ser-zones` that returns all stored SER zones as a list suitable for map rendering
- Introduce a React SPA (`frontend/`) served separately from the FastAPI backend, with a single map page that renders zones as coloured markers over a self-hosted OpenStreetMap tile server
- Add `OSM_TILE_URL` environment variable (backend exposes it via `GET /config`); frontend fetches it at startup so the tile server can be changed without a rebuild
- Add `CORS_ORIGINS` support for the frontend origin (already exists in config but needs the frontend URL added)
- Use **pnpm** as the package manager for the frontend project
- Add **Playwright** end-to-end tests covering the map page (markers visible, tooltip content, tile layer loading)
- Extend `docker-compose.yml` with a `frontend` service so the full stack (backend + database + frontend) starts with a single `docker-compose up`

## Capabilities

### New Capabilities

- `zone-colour`: Colour assignment for zone types in the domain layer — `ZoneType.colour` property returning a hex string; `MadridZoneType` maps Azul → `#2563EB`, Verde → `#16A34A`, others → `#6B7280`
- `zones-bulk-query`: New API endpoint `GET /parking/ser-zones?city=madrid` returning all zones (street name, zone type, colour, spot count, lat, lng) — pagination optional for now, full list acceptable given current data size
- `osm-zone-map`: React SPA with a single map view — fetches tile URL from `/config`, fetches all zones from `/parking/ser-zones`, renders coloured circle markers with a tooltip showing street name, zone type, and spot count

### Modified Capabilities

- `ser-zone-query`: No requirement change — existing `GET /parking/ser-zone` endpoint behaviour is unchanged

## Impact

- **Domain**: `domain/value_objects/zone_type.py`, `infrastructure/parking_services/madrid/zone_type.py`
- **API**: new router `presentation/api/routers/zones.py`; new schema fields; new `GET /config` endpoint
- **Config**: `config.py` — new `get_osm_tile_url()` function
- **Frontend**: new `frontend/` directory (React + Vite + TypeScript + react-leaflet + Tailwind CSS)
- **Dependencies**: `requirements.txt` unchanged; new `frontend/package.json` managed with pnpm (React, Vite, react-leaflet, Tailwind, Playwright)
- **Docker**: `docker-compose.yml` gains a `frontend` service (multi-stage build: Node/pnpm for build, nginx for serving); full stack starts with `docker-compose up`
