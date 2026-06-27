## 1. Add Alembic dependency

- [x] 1.1 Add `alembic` to `requirements.txt`
- [x] 1.2 Install it in the virtualenv (`pip install alembic`) and verify `alembic --version` works

## 2. Extract shared table metadata

- [x] 2.1 Create `src/mobility_manager/infrastructure/orm/__init__.py` (empty)
- [x] 2.2 Create `src/mobility_manager/infrastructure/orm/tables.py` with the shared `MetaData` instance and `ser_zones_table` Table definition (copied from `ser_zone_repo.py`)
- [x] 2.3 Update `src/mobility_manager/infrastructure/repositories/postgres/ser_zone_repo.py` to import `ser_zones_table` and `metadata` from `infrastructure/orm/tables.py` instead of defining them locally

## 3. Initialise Alembic scaffold

- [x] 3.1 Run `alembic init alembic` in the project root to generate `alembic.ini` and `alembic/` directory
- [x] 3.2 Edit `alembic/env.py`: import `get_postgres_dsn` from `mobility_manager.config` and set `config.set_main_option("sqlalchemy.url", get_postgres_dsn())` before `run_migrations_offline()` / `run_migrations_online()` are called
- [x] 3.3 Edit `alembic/env.py`: import `metadata` from `mobility_manager.infrastructure.orm.tables` and set `target_metadata = metadata`
- [x] 3.4 Edit `alembic.ini`: set `sqlalchemy.url =` (empty) to make clear it is overridden at runtime; add a comment explaining it is set in `env.py`

## 4. Generate initial migration

- [x] 4.1 Run `alembic revision --autogenerate -m "create_ser_zones"` to generate the initial migration script
- [x] 4.2 Review the generated script in `alembic/versions/` and verify it contains `CREATE TABLE ser_zones` with all 8 columns (id, street_name, zone_code, zone_label, latitude, longitude, utm_x, utm_y)
- [x] 4.3 Add `op.create_index("idx_ser_zones_coords", "ser_zones", ["latitude", "longitude"])` to the `upgrade()` function if autogenerate did not include it
- [x] 4.4 Add a `downgrade()` function that drops the index and table in reverse order

## 5. Update Makefile

- [x] 5.1 Replace the existing `db-migrate` target body with `$(VENV)/bin/alembic upgrade head`
- [x] 5.2 Add `db-revision` target: `$(VENV)/bin/alembic revision --autogenerate -m "$(msg)"`
- [x] 5.3 Add both targets to the `.PHONY` list
- [x] 5.4 Add a comment above `db-revision` explaining that callers must set `msg=<description>`, e.g. `make db-revision msg="add_vehicle_table"`

## 6. Remove old migration artefacts

- [x] 6.1 Delete `db/migrations/001_create_ser_zones.sql`
- [x] 6.2 Delete the `db/` directory (it will be empty after 6.1)

## 7. Container startup entrypoint

- [x] 7.1 Create `docker-entrypoint.sh`: run `alembic upgrade head` then `exec uvicorn mobility_manager.presentation.api.app:app --host 0.0.0.0 --port 8000`
- [x] 7.2 Make `docker-entrypoint.sh` executable (`chmod +x`)
- [x] 7.3 Update `Dockerfile`: add `COPY alembic/ alembic/`, `COPY alembic.ini .`, `COPY docker-entrypoint.sh .`; replace `CMD` with `ENTRYPOINT ["./docker-entrypoint.sh"]`

## 8. Verify

- [x] 8.1 Run `make db-migrate` against a local PostgreSQL instance (or Docker) and confirm `ser_zones` table and `alembic_version` table are created
- [x] 8.2 Run `alembic downgrade -1` and confirm both `ser_zones` and `idx_ser_zones_coords` are dropped
- [x] 8.3 Run `alembic upgrade head` again to confirm re-apply works cleanly
