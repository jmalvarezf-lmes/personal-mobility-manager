### Requirement: Alembic scaffold is present and configured
The project SHALL include a complete Alembic scaffold (`alembic.ini` and `alembic/env.py`) that resolves the database URL from the `POSTGRES_DSN` environment variable at runtime. No DSN SHALL be hardcoded in any configuration file.

#### Scenario: Running alembic with POSTGRES_DSN set
- **WHEN** `POSTGRES_DSN` is set in the environment and `alembic upgrade head` is executed
- **THEN** Alembic connects to the target PostgreSQL database without error

#### Scenario: Running alembic without POSTGRES_DSN
- **WHEN** `POSTGRES_DSN` is not set and any alembic command is executed
- **THEN** The process exits with a clear error referencing the missing environment variable

---

### Requirement: Single metadata source for all SQLAlchemy tables
All SQLAlchemy `Table` definitions and the shared `MetaData` instance SHALL live in `src/mobility_manager/infrastructure/orm/tables.py`. Repository files SHALL NOT define their own `MetaData` or `Table` objects; they SHALL import from `tables.py` instead.

#### Scenario: Alembic autogenerate discovers all tables
- **WHEN** `alembic revision --autogenerate` is run against a clean database
- **THEN** the generated script contains DDL for every table defined in `tables.py` and no extra tables

#### Scenario: Repository imports shared table definition
- **WHEN** `PostgresSerZoneRepository` is instantiated
- **THEN** it uses the `ser_zones_table` object imported from `infrastructure/orm/tables.py`, not a locally defined copy

---

### Requirement: Initial migration creates the ser_zones table
An Alembic migration script SHALL exist in `alembic/versions/` that creates the `ser_zones` table with all columns and the `idx_ser_zones_coords` index, exactly matching the schema defined in `tables.py`.

#### Scenario: Fresh database migration
- **WHEN** a fresh PostgreSQL database has no tables and `alembic upgrade head` is executed
- **THEN** the `ser_zones` table exists with columns: id, street_name, zone_code, zone_label, latitude, longitude, utm_x, utm_y
- **THEN** the index `idx_ser_zones_coords` on (latitude, longitude) exists

#### Scenario: Migration is reversible
- **WHEN** `alembic downgrade -1` is executed after the initial migration
- **THEN** the `ser_zones` table and its index are dropped without error

---

### Requirement: Makefile exposes migration commands
The Makefile SHALL provide two targets for database schema management:
- `db-migrate`: applies all pending migrations (`alembic upgrade head`)
- `db-revision msg=<message>`: generates a new autogenerate migration script

#### Scenario: Developer applies migrations
- **WHEN** a developer runs `make db-migrate` with `POSTGRES_DSN` set
- **THEN** all pending Alembic migrations are applied to the target database

#### Scenario: Developer generates a new migration
- **WHEN** a developer runs `make db-revision msg="add_foo_table"` after adding a new `Table` to `tables.py`
- **THEN** a new versioned migration file is created in `alembic/versions/` with a `create_foo_table`-style message

---

### Requirement: Container startup applies pending migrations automatically
The project SHALL include a `docker-entrypoint.sh` script that runs `alembic upgrade head` before starting the application server. The `Dockerfile` SHALL use this script as its `ENTRYPOINT` and SHALL copy `alembic/` and `alembic.ini` into the image. If migration fails the container SHALL exit with a non-zero code and the server SHALL NOT start.

#### Scenario: Container starts with a clean database
- **WHEN** the Docker container starts with `POSTGRES_DSN` pointing to a database with no tables
- **THEN** `alembic upgrade head` runs and creates all tables before uvicorn accepts any request

#### Scenario: Container starts with an up-to-date database
- **WHEN** the Docker container starts and all migrations are already applied
- **THEN** `alembic upgrade head` is a no-op and uvicorn starts normally

#### Scenario: Migration fails on container startup
- **WHEN** the Docker container starts and `alembic upgrade head` exits with an error
- **THEN** the container exits with a non-zero code and uvicorn does not start

---

### Requirement: alembic_version table tracks applied migrations
After any `alembic upgrade` run the database SHALL contain an `alembic_version` table that records the current head revision.

#### Scenario: Version is stamped after upgrade
- **WHEN** `alembic upgrade head` completes successfully
- **THEN** `SELECT version_num FROM alembic_version` returns the current head revision ID

---

### Requirement: ON DELETE CASCADE on vehicle child table foreign keys
A new Alembic migration SHALL alter the `vehicle_configs.vehicle_id` and `vehicle_locations.vehicle_id` foreign key constraints to add `ON DELETE CASCADE`. After this migration, deleting a row from `vehicles` SHALL automatically delete all associated rows in `vehicle_configs` and `vehicle_locations`.

#### Scenario: Deleting a vehicle cascades to vehicle_configs
- **WHEN** a vehicle row is deleted from the `vehicles` table
- **THEN** the corresponding `vehicle_configs` row (if any) is automatically deleted

#### Scenario: Deleting a vehicle cascades to vehicle_locations
- **WHEN** a vehicle row is deleted from the `vehicles` table
- **THEN** all `vehicle_locations` rows with that `vehicle_id` are automatically deleted

#### Scenario: Migration is reversible
- **WHEN** `alembic downgrade -1` is executed after applying the cascade migration
- **THEN** the foreign key constraints revert to their previous state (no cascade) without error

#### Scenario: Existing rows are not affected
- **WHEN** the cascade migration is applied to a database with existing vehicles, configs, and locations
- **THEN** all existing rows are preserved unchanged; only the FK constraint definition changes
