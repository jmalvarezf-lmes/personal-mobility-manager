"""
Infrastructure: SQLAlchemy engine factory.

Provides a singleton engine instance configured from POSTGRES_DSN.
"""

import logging
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from mobility_manager.config import _mask_dsn_password, get_postgres_dsn

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return a cached SQLAlchemy engine configured from POSTGRES_DSN."""
    logger.debug("Creating DB engine for %s", _mask_dsn_password(get_postgres_dsn()))
    return create_engine(get_postgres_dsn(), pool_pre_ping=True)
