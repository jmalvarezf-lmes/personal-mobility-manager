## Context

The project uses Clean Architecture (Python 3.12, pip, src layout). Madrid SER data is currently a stub in `infrastructure/parking_services/madrid/`. The Madrid Open Data portal publishes a callejero CSV containing street records with ETRS89/UTM GIS coordinates and associated SER zone codes. We need to download, reproject, store, and query this data efficiently.

Current state: `ParkingServicePort` is an empty ABC; `GeoLocation` value object is a stub; no database layer exists yet.

## Goals / Non-Goals

**Goals:**
- Periodic ingestion of Madrid callejero CSV → PostgreSQL (upsert, idempotent)
- Coordinate-to-SER-zone lookup via REST API (nearest street segment, sub-100ms at P99 for warm cache)
- Clean Architecture boundaries preserved: domain knows nothing about Postgres or HTTP
- Docker Compose adds a Postgres service; Makefile gets `db-migrate` and `scheduler` targets

**Non-Goals:**
- Real-time streaming updates (batch ingestion is sufficient)
- Multi-city SER data in this change (architecture supports it; Madrid only now)
- Authentication on the API (internal tool, no auth layer in this change)
- PostGIS extension required (we use Haversine + indexed bounding box; PostGIS is optional)

## Decisions

### D1: Coordinate storage — lat/lng columns vs PostGIS geometry

**Decision**: Store `latitude DOUBLE PRECISION` and `longitude DOUBLE PRECISION` columns with a composite index. Use Haversine distance in a bounded SQL query (bounding box filter + Python distance sort) for nearest-street lookup.

**Why not PostGIS**: Requires PostGIS extension, heavier ops dependency. The dataset has ~100k rows max; bounding-box + Haversine in Python is fast enough (<50ms) without the extension dependency.

**Alternative considered**: Store WKT geometry string + PostGIS `ST_DWithin`. Revisit if the dataset grows beyond 500k rows or if sub-10ms latency becomes a requirement.

### D2: Coordinate reprojection — pyproj

**Decision**: Use `pyproj.Transformer` to reproject from ETRS89 UTM Zone 30N (EPSG:25830) to WGS84 (EPSG:4326) during ingestion. Store only WGS84 lat/lng in the database.

**Why**: The CSV exports coordinates in ETRS89/UTM; all client queries will come in WGS84 (GPS). Reprojecting once at ingest is cheaper than at query time. `pyproj` wraps PROJ and is the standard Python choice.

### D3: Scheduler — APScheduler with interval trigger

**Decision**: Use `APScheduler` (`BackgroundScheduler`, interval trigger, default 24h). The scheduler runs inside the same FastAPI process on startup using the `lifespan` context manager.

**Why not a separate cron job**: Keeps deployment simple (one container). Cron requires shell access and separate orchestration. APScheduler is lightweight and already integrates with FastAPI lifespan.

**Alternative considered**: Celery + Redis for distributed scheduling. Overkill for a single-task, single-node use case.

### D4: HTTP framework — FastAPI

**Decision**: Use FastAPI for the REST API layer (`presentation/api/`).

**Why**: Consistent with the project's stated direction (Clean Architecture + FastAPI noted in prior sessions). Async-first, automatic OpenAPI docs, minimal boilerplate.

### D5: Database access — SQLAlchemy Core (not ORM)

**Decision**: Use SQLAlchemy Core with a single `ser_zones` table. No ORM models — only `Table` definitions and `Connection.execute()`.

**Why**: The domain entities are pure Python dataclasses. Introducing ORM models would create a second class hierarchy that mirrors the domain, violating Clean Architecture. SQLAlchemy Core gives parameterized queries and connection pooling without bleeding ORM concepts into the domain.

### D6: Ingestion strategy — full replace vs upsert

**Decision**: Truncate-and-reload strategy: on each scheduler run, download → parse → begin transaction → truncate `ser_zones` → bulk insert → commit. If any step fails, the transaction rolls back and the old data stays.

**Why**: The dataset is city-provided and authoritative; no partial updates are meaningful. Truncate-reload is simpler than composite-key upsert and guarantees consistency. At ~100k rows the bulk insert completes in <2s.

## Risks / Trade-offs

- **Madrid Open Data URL changes** → Mitigation: make the URL configurable via env var `MADRID_CALLEJERO_URL`; log a clear error if the download fails and keep stale data.
- **Large CSV parsing memory** → Mitigation: stream-parse with `csv.reader` row by row; never load the full file into memory.
- **Nearest-street lookup accuracy** → Trade-off: bounding-box + Haversine finds the nearest street centroid, not the nearest point on a street segment. Acceptable for SER zone lookup (zone boundaries are at street level, not sub-meter).
- **Schema changes in source CSV** → Mitigation: parse defensively with column-name lookup (not positional index); log and skip rows with unexpected structure.

## Migration Plan

1. Add `postgres` service to `docker-compose.yml` (image: `postgres:16-alpine`).
2. Add `db-migrate` Makefile target that runs `alembic upgrade head` (or inline DDL script).
3. On first deploy: `make db-migrate` creates `ser_zones` table; first scheduler tick populates data.
4. Rollback: `make db-downgrade` drops `ser_zones`; remove the API container.

## Open Questions

- What SER zone codes appear in the CSV? Need to inspect the dataset to map raw codes to human-readable labels (Blue, Green, etc.). The ingestion layer will store the raw code and a normalized label; the mapping will be a small lookup dict derived from the first ingestion run.
- Should the API return multiple zone types if the queried point is near a zone boundary? Decision deferred to implementation; initial version returns the single nearest street's zone.
