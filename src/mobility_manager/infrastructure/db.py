"""
Infrastructure: SQLAlchemy engine factory.

Provides a singleton engine instance configured from POSTGRES_DSN.
"""
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from mobility_manager.config import get_postgres_dsn


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return a cached SQLAlchemy engine configured from POSTGRES_DSN."""
    return create_engine(get_postgres_dsn(), pool_pre_ping=True)
