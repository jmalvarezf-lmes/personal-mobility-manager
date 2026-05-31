## Why

To determine whether a parked vehicle is inside a Madrid SER (Servicio de Estacionamiento Regulado) zone — and which type — we need local, queryable SER zone data. The Madrid Open Data platform provides a street-level dataset with SER zone associations and GIS coordinates, but it must be downloaded, parsed, and stored to be useful at query time.

## What Changes

- **New scheduler**: periodic job that fetches the Madrid callejero CSV from `datos.madrid.es`, parses GIS coordinates (ETRS89 / UTM to WGS84), extracts street + SER zone type, and upserts into PostgreSQL.
- **New PostgreSQL schema**: `ser_zones` table storing street name, SER zone type (Blue, Green, etc.), and geometry (PostGIS point/polygon or lat/lng columns) with a spatial index.
- **New REST API**: FastAPI endpoint `GET /parking/ser-zone?lat=&lng=` that returns the SER zone type for the nearest matching street segment.
- **Domain enrichment**: `SerZone` entity and `SerZoneRepository` port added to domain layer; `ParkingServicePort` extended or left parallel.
- **Infrastructure adapter**: PostgreSQL `SerZoneRepository` implementation and HTTP Madrid data fetcher.

## Capabilities

### New Capabilities
- `ser-zone-ingestion`: Scheduler that downloads the Madrid callejero CSV, parses GIS coordinates, and upserts SER zone data (street, zone type, coordinates) into PostgreSQL.
- `ser-zone-query`: REST API (FastAPI) exposing a coordinate-based lookup endpoint that returns the SER zone type for a given lat/lng.

### Modified Capabilities

## Impact

- **New dependencies**: `fastapi`, `uvicorn`, `psycopg2-binary` (or `asyncpg`), `sqlalchemy`, `pyproj` (ETRS89→WGS84 reprojection), `apscheduler` (or cron), `httpx` for CSV download.
- **PostgreSQL**: requires a running Postgres instance; optionally PostGIS extension for spatial queries (fallback: Haversine distance in Python).
- **New files**: `src/mobility_manager/domain/entities/ser_zone.py`, `src/mobility_manager/domain/ports/ser_zone_repository.py`, `src/mobility_manager/infrastructure/parking_services/madrid/data_fetcher.py`, `src/mobility_manager/infrastructure/repositories/postgres/ser_zone_repo.py`, `src/mobility_manager/presentation/api/`.
- **Docker / Makefile**: PostgreSQL service added to `docker-compose.yml`; migration target added to `Makefile`.
