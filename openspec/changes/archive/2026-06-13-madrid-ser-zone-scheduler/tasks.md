## 1. Dependencies & Infrastructure Setup

- [x] 1.1 Add `fastapi`, `uvicorn[standard]`, `sqlalchemy`, `psycopg2-binary`, `pyproj`, `apscheduler`, `httpx` to `requirements.txt`
- [x] 1.2 Add `postgres:16-alpine` service to `docker-compose.yml` with env vars `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` and a named volume
- [x] 1.3 Add `POSTGRES_DSN` and `MADRID_CALLEJERO_URL` and `INGESTION_INTERVAL_HOURS` env vars to `.env.example` and `src/mobility_manager/config.py`
- [x] 1.4 Create `db/migrations/001_create_ser_zones.sql` with `CREATE TABLE IF NOT EXISTS ser_zones` DDL (id, street_name, zone_code, zone_label, latitude, longitude) and composite index on (latitude, longitude)
- [x] 1.5 Add `db-migrate` and `api` targets to `Makefile`

## 2. Domain Layer

- [x] 2.1 Implement `GeoLocation` value object in `src/mobility_manager/domain/value_objects/location.py` with `lat: float` and `lng: float` fields and bounds validation
- [x] 2.2 Create `src/mobility_manager/domain/entities/ser_zone.py` — `SerZone` dataclass with `street_name`, `zone_code`, `zone_label`, `location: GeoLocation`
- [x] 2.3 Create `src/mobility_manager/domain/exceptions.py` — `SerZoneNotFoundError` domain exception
- [x] 2.4 Create `src/mobility_manager/domain/ports/ser_zone_repository.py` — `SerZoneRepository` ABC with `find_nearest(location: GeoLocation, radius_deg: float) -> SerZone | None`

## 3. Application Layer

- [x] 3.1 Create `src/mobility_manager/application/use_cases/find_nearest_ser_zone.py` — `FindNearestSerZone` use case accepting `SerZoneRepository`, calling `find_nearest`, raising `SerZoneNotFoundError` if `None`
- [x] 3.2 Create `src/mobility_manager/application/use_cases/ingest_ser_zones.py` — `IngestSerZones` use case stub (orchestrates download → parse → persist; depends on infrastructure ports injected at runtime)

## 4. Infrastructure — Data Fetcher & Parser

- [x] 4.1 Create `src/mobility_manager/infrastructure/parking_services/madrid/data_fetcher.py` — `MadridCallejeroCsvFetcher` that downloads the CSV via `httpx` (streaming), returns a `io.StringIO` or line iterator
- [x] 4.2 Create `src/mobility_manager/infrastructure/parking_services/madrid/csv_parser.py` — `CallejeroCsvParser` that reads rows by column name, extracts `NOMBRE_VIA`, SER zone code column, and UTM X/Y columns; skips rows with missing fields; returns list of raw dicts
- [x] 4.3 Implement coordinate reprojection in `csv_parser.py` using `pyproj.Transformer.from_crs("EPSG:25830", "EPSG:4326")` to convert UTM X/Y → WGS84 lat/lng
- [x] 4.4 Implement zone code → label mapping dict in `csv_parser.py` (derive mapping from first real CSV inspection; store unknown codes as-is)

## 5. Infrastructure — PostgreSQL Repository

- [x] 5.1 Create `src/mobility_manager/infrastructure/repositories/__init__.py` and `src/mobility_manager/infrastructure/repositories/postgres/__init__.py`
- [x] 5.2 Create `src/mobility_manager/infrastructure/repositories/postgres/ser_zone_repo.py` — `PostgresSerZoneRepository` implementing `SerZoneRepository`; `find_nearest` uses bounding-box SQL filter then Haversine sort in Python; expands box 2× if no result
- [x] 5.3 Implement `bulk_replace(records: list[dict])` method on `PostgresSerZoneRepository` — truncate + bulk insert in one transaction
- [x] 5.4 Create `src/mobility_manager/infrastructure/db.py` — SQLAlchemy `create_engine` factory reading `POSTGRES_DSN` from config; expose `get_engine()` singleton

## 6. Infrastructure — Scheduler

- [x] 6.1 Create `src/mobility_manager/infrastructure/scheduler.py` — `SerZoneIngestionScheduler` wrapping `APScheduler.BackgroundScheduler`; `start()` schedules `IngestSerZones` with interval from config; `stop()` shuts down cleanly

## 7. Presentation — FastAPI

- [x] 7.1 Create `src/mobility_manager/presentation/api/__init__.py` and `src/mobility_manager/presentation/api/app.py` — FastAPI app with `lifespan` context manager that starts/stops the scheduler
- [x] 7.2 Create `src/mobility_manager/presentation/api/routers/parking.py` — `GET /parking/ser-zone` endpoint with `lat` and `lng` query params; validates bounds; calls `FindNearestSerZone`; maps `SerZoneNotFoundError` → 404
- [x] 7.3 Create `src/mobility_manager/presentation/api/schemas.py` — `SerZoneResponse` Pydantic model with `street_name`, `zone_code`, `zone_label`, `distance_meters`, `latitude`, `longitude`
- [x] 7.4 Wire dependency injection in `app.py`: create engine → repo → use case instances; pass via FastAPI `Depends` or state

## 8. Tests

- [x] 8.1 Unit test `GeoLocation` validation (invalid lat/lng raises `ValueError`)
- [x] 8.2 Unit test `FindNearestSerZone` use case with mock repository (found → returns `SerZone`; not found → raises `SerZoneNotFoundError`)
- [x] 8.3 Unit test `CallejeroCsvParser` with fixture CSV rows: valid row parsed correctly, missing zone code skipped, invalid coordinates skipped
- [x] 8.4 Unit test coordinate reprojection: known Madrid UTM point → expected WGS84 lat/lng within 0.0001 degrees
- [x] 8.5 Integration test `PostgresSerZoneRepository.find_nearest` against a real Postgres test DB (use pytest fixture with `POSTGRES_DSN` from env or skip if not available)
- [x] 8.6 Integration test `GET /parking/ser-zone` via FastAPI `TestClient` with seeded database: valid coords return 200, empty DB returns 404, bad params return 422
