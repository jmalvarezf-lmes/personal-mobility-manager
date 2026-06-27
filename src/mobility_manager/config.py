"""
Application configuration loaded from environment variables.
"""
import os
import re

from dotenv import load_dotenv

load_dotenv()

_DEFAULT_MADRID_SER_CALLES_URL = (
    "https://datos.madrid.es/dataset/218228-0-ser-calles/resource/"
    "218228-1-ser-calles-csv/download/218228-1-ser-calles-csv.csv"
)


def get_postgres_dsn() -> str:
    """Return the PostgreSQL connection DSN from environment."""
    dsn = os.environ.get("POSTGRES_DSN")
    if not dsn:
        raise RuntimeError("POSTGRES_DSN environment variable is not set")
    return dsn


def get_madrid_ser_calles_url() -> str:
    """Return the Madrid SER Calles CSV URL from environment."""
    return os.environ.get("MADRID_SER_CALLES_URL", _DEFAULT_MADRID_SER_CALLES_URL)


def get_ingestion_interval_hours() -> int:
    """Return the ingestion interval in hours from environment."""
    raw = os.environ.get("INGESTION_INTERVAL_HOURS", "24")
    try:
        return int(raw)
    except ValueError:
        return 24


def _mask_dsn_password(dsn: str) -> str:
    """Replace password in DSN with *** for safe logging."""
    return re.sub(r"(://[^:@/]+:)[^@]+(@)", r"\1***\2", dsn)


def get_cors_origins() -> list[str]:
    """Return allowed CORS origins from CORS_ORIGINS env var (comma-separated)."""
    raw = os.environ.get("CORS_ORIGINS", "")
    return [o.strip() for o in raw.split(",") if o.strip()]
