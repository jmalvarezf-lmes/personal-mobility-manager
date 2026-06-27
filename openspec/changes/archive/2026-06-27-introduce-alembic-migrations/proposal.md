## Why

The project's PostgreSQL schema (`ser_zones` table and any future tables) is currently managed with raw SQLAlchemy `MetaData` / `Table` objects defined inside repository files, with no migration tool in place. As the schema evolves — new tables, column changes, indexes — there is no safe, repeatable way to apply those changes to existing databases without manual DDL intervention. Alembic is the standard migration tool for SQLAlchemy projects and will give us versioned, idempotent schema evolution from day one.

## What Changes

- Add `alembic` to `requirements.txt`.
- Create `alembic/` directory at the project root with `alembic.ini` and the `env.py` configured to use the project's `POSTGRES_DSN` setting and share the SQLAlchemy `MetaData` from the infrastructure layer.
- Extract the SQLAlchemy `MetaData` and `Table` definitions out of `ser_zone_repo.py` into a dedicated `src/mobility_manager/infrastructure/orm/tables.py` module so Alembic's autogenerate can discover all table definitions in one place.
- Generate and commit an initial migration script that creates the `ser_zones` table (replaces the implicit `metadata.create_all()` approach).
- Update `Makefile` with `db-migrate` and `db-revision` targets.
- Add `docker-entrypoint.sh` that runs `alembic upgrade head` before starting the application, ensuring migrations are always applied on container startup.
- Update `Dockerfile` to use the entrypoint script and copy `alembic/` and `alembic.ini` into the image.

## Capabilities

### New Capabilities

- `schema-migrations`: Versioned, Alembic-managed SQL migrations. Covers the `alembic/` scaffold, `alembic.ini`, `env.py`, a shared `tables.py` metadata module, and the initial migration for the `ser_zones` table. Provides `db-migrate` / `db-revision` Makefile targets.

### Modified Capabilities

## Impact

- `requirements.txt` — add `alembic`
- `src/mobility_manager/infrastructure/orm/tables.py` — new shared metadata module (extracted from `ser_zone_repo.py`)
- `src/mobility_manager/infrastructure/repositories/postgres/ser_zone_repo.py` — imports `ser_zones_table` from `tables.py` instead of defining it locally
- `alembic/` — new directory: `alembic.ini`, `env.py`, `versions/`
- `Makefile` — new `db-migrate` and `db-revision` targets
- `docker-entrypoint.sh` — new file; runs migrations then starts uvicorn
- `Dockerfile` — copies `alembic/`, `alembic.ini`, `docker-entrypoint.sh`; switches from `CMD` to `ENTRYPOINT`
- No API or domain changes; this is a pure infrastructure concern
