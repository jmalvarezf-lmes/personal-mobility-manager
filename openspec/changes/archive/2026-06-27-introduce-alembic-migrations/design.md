## Context

The project currently manages its PostgreSQL schema through a hand-written SQL file (`db/migrations/001_create_ser_zones.sql`) applied via a raw `psql` call in the Makefile. The `ser_zones` table is defined a second time using SQLAlchemy Core `Table()` / `MetaData()` inside `ser_zone_repo.py`, creating a divergence risk between the DDL and the ORM layer. There is no versioning, no idempotent upgrade/downgrade path, and no autogenerate capability as new tables are added. SQLAlchemy is already installed; Alembic (the official SQLAlchemy migration tool) is the natural fit.

## Goals / Non-Goals

**Goals:**
- Single source of truth for table definitions: a shared `tables.py` module that both the repository code and Alembic `env.py` import.
- Alembic scaffold (`alembic.ini`, `alembic/env.py`, `alembic/versions/`) configured to read `POSTGRES_DSN` from the environment (same as the app).
- Initial migration script that replaces `001_create_ser_zones.sql` (creates `ser_zones` table + index).
- Makefile targets that wrap `alembic upgrade head` and `alembic revision --autogenerate`.
- Delete `db/migrations/001_create_ser_zones.sql` and the `db/` directory — the project is new and has no existing databases to preserve.
- `docker-entrypoint.sh` that runs `alembic upgrade head` then starts uvicorn, so migrations are always applied on container startup.
- Update `Dockerfile` to use the entrypoint and include the Alembic files in the image.

**Non-Goals:**
- Switching from SQLAlchemy Core to ORM / declarative models — repositories continue using `Table()` objects.
- Multi-database or multi-tenant migration support.
- CI/CD pipeline changes (out of scope for this change).
- Async SQLAlchemy (`create_async_engine`) — the app currently uses the synchronous engine.

## Decisions

### D1 — Shared `tables.py` as single source of truth

**Decision**: Move `ser_zones_table` and `metadata` from `ser_zone_repo.py` to `src/mobility_manager/infrastructure/orm/tables.py`. Both `ser_zone_repo.py` and Alembic `env.py` import from there.

**Why**: Alembic's `--autogenerate` compares live DB schema against the `MetaData` object. If `MetaData` is buried inside a repository class, Alembic cannot discover it without importing the whole repo. A dedicated `tables.py` is a clean, zero-ORM surface for migration discovery.

**Alternatives considered**:
- Importing `MetaData` directly from `ser_zone_repo.py` in `env.py` — works but couples the migration tool to a repository file, which is the wrong layer.
- Switching to declarative ORM Base — too large a change; Core Table objects already serve the project well.

### D2 — `alembic.ini` reads DSN from environment variable

**Decision**: Configure `sqlalchemy.url` in `alembic.ini` to an empty placeholder; override it in `env.py` by calling `get_postgres_dsn()` at migration-run time.

**Why**: Hardcoding a DSN in `alembic.ini` is a security risk and breaks per-environment deployments. The existing `config.py` already centralises DSN resolution from `POSTGRES_DSN` env var — reuse it.

**Alternatives considered**:
- Setting `%POSTGRES_DSN%` placeholder directly in `alembic.ini` — Alembic does not interpolate env vars in `.ini` files without extra plugins.

### D3 — Replace `db-migrate` Makefile target; keep `db-revision`

**Decision**: Redefine `db-migrate` to call `alembic upgrade head`. Add `db-revision` as `alembic revision --autogenerate -m "$(msg)"`.

**Why**: The existing `db-migrate` target name is already used by the team; keeping the same name avoids workflow churn. `db-revision` is the new companion for generating migrations from model changes.

### D5 — Container startup runs migrations via entrypoint script

**Decision**: Add `docker-entrypoint.sh` that calls `alembic upgrade head` and then `exec uvicorn ...`. The Dockerfile uses this as `ENTRYPOINT` instead of the previous `CMD ["mobility-manager"]`.

**Why**: Migrations must complete before the application accepts traffic. The entrypoint approach enforces this ordering at the process level — if migration fails, the container exits with a non-zero code and the server never starts. Using `exec` is required so uvicorn inherits the shell's PID and receives OS signals (e.g., SIGTERM on `docker stop`) directly.

**Alternatives considered**:
- Calling `alembic upgrade head` programmatically inside the FastAPI `lifespan` — works, but puts an infrastructure concern (Alembic) inside the presentation layer, violating Clean Architecture. Also harder to observe as a distinct startup step.
- Kubernetes init container — valid for K8s deployments; the entrypoint script is simpler and works for both plain Docker and orchestrated environments.

### D4 — Initial migration is the authoritative schema source

**Decision**: Generate an initial Alembic migration that creates the `ser_zones` table and its index. Delete `db/migrations/001_create_ser_zones.sql` and the `db/` directory entirely — the project has no existing databases, so there is nothing to stamp or preserve.

**Why**: The project is new; no environment has the old `psql`-applied schema. A clean break avoids confusion about which migration path is canonical.

## Risks / Trade-offs

- **`tables.py` import in `env.py` drags in project dependencies** (pyproj, psycopg2, etc.) at migration time → acceptable; these are already in requirements. If this ever becomes a problem, use a lightweight metadata-only module without imports.
- **Autogenerate is not fully exhaustive** — Alembic cannot detect certain changes (e.g., check constraints, server defaults with expressions). Mitigation: always review generated migration scripts before committing.

## Migration Plan

1. `pip install alembic` (add to `requirements.txt`).
2. Extract `metadata` + `ser_zones_table` into `src/mobility_manager/infrastructure/orm/tables.py`.
3. Update `ser_zone_repo.py` to import from `tables.py`.
4. Run `alembic init alembic` (creates scaffold).
5. Edit `alembic/env.py` to import `metadata` from `tables.py` and resolve DSN from `get_postgres_dsn()`.
6. Run `alembic revision --autogenerate -m "create_ser_zones"` to generate the initial migration.
7. Review generated script; adjust to match the schema in `tables.py` exactly (including index).
8. Delete `db/migrations/001_create_ser_zones.sql` and the `db/` directory.
9. Update `Makefile`.
10. Create `docker-entrypoint.sh`; update `Dockerfile` to copy Alembic files and use the entrypoint.
11. Run `alembic upgrade head` to verify on a clean database.

**Rollback**: `alembic downgrade -1` (if a `downgrade()` function is provided in the migration script). The initial migration's downgrade drops `ser_zones`.

## Open Questions

None.
