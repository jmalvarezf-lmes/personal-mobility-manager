from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from mobility_manager.config import get_postgres_dsn
from mobility_manager.infrastructure.orm.tables import metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject DSN from the application config so nothing is hardcoded in alembic.ini.
config.set_main_option("sqlalchemy.url", get_postgres_dsn())

target_metadata = metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout, no live DB needed)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connect to live DB)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
