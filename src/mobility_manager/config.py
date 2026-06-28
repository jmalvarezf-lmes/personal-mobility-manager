"""
Application configuration loaded from environment variables.
"""
import os
import re
from typing import Any

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


def get_osm_tile_url() -> str | None:
    """Return the OSM tile server URL from environment, or None if unset."""
    return os.environ.get("OSM_TILE_URL") or None


def get_enabled_brands() -> list[Any]:  # list[Brand] — avoids circular import at module level
    """
    Return the list of enabled vehicle brands from ENABLED_BRANDS env var.

    Parses the comma-separated string and validates each value against the
    Brand enum. Unknown values are silently ignored.
    Default is ["generic"] when ENABLED_BRANDS is not set.
    """
    from mobility_manager.domain.value_objects.brand import Brand

    raw = os.environ.get("ENABLED_BRANDS", "generic")
    result: list[Brand] = []
    for code in raw.split(","):
        code = code.strip().lower()
        if not code:
            continue
        try:
            result.append(Brand(code))
        except ValueError:
            pass  # unknown brand code — ignored
    return result


def get_encryption_key() -> bytes:
    """
    Return the Fernet encryption key from ENCRYPTION_KEY env var.

    The value must be a base64-encoded 32-byte key as produced by
    ``Fernet.generate_key()``.

    Raises:
        RuntimeError: If ENCRYPTION_KEY is not set.
    """
    key = os.environ.get("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY environment variable is not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return key.encode()


def get_vehicle_poll_interval_minutes() -> int:
    """Return the vehicle location poll interval in minutes from environment."""
    raw = os.environ.get("VEHICLE_POLL_INTERVAL_MINUTES", "5")
    try:
        return int(raw)
    except ValueError:
        return 5
