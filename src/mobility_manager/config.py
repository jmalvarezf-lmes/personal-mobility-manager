"""
Application configuration loaded from environment variables.
"""

import contextlib
import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def get_postgres_dsn() -> str:
    """Return the PostgreSQL connection DSN from environment."""
    dsn = os.environ.get("POSTGRES_DSN")
    if not dsn:
        raise RuntimeError("POSTGRES_DSN environment variable is not set")
    return dsn


def get_ingestion_interval_hours() -> int:
    """Return the ingestion interval in hours from environment."""
    raw = os.environ.get("INGESTION_INTERVAL_HOURS", "24")
    try:
        return int(raw)
    except ValueError:
        return 24


def get_log_level() -> str:
    """Return the root logging level from environment (default INFO)."""
    raw = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
    return raw if raw in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"} else "INFO"


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


def get_toyota_locale() -> str:
    """Return the default Toyota account locale from TOYOTA_LOCALE, or 'en_GB' if unset."""
    return os.environ.get("TOYOTA_LOCALE") or "en_GB"


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
        with contextlib.suppress(ValueError):
            result.append(Brand(code))
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
            'Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    return key.encode()


def get_vehicle_poll_interval_minutes() -> int:
    """Return the vehicle location poll interval in minutes from environment."""
    raw = os.environ.get("VEHICLE_POLL_INTERVAL_MINUTES", "5")
    try:
        return int(raw)
    except ValueError:
        return 5


def get_notification_movement_threshold_meters() -> float:
    """Return the minimum movement distance (metres) that triggers a location notification."""
    raw = os.environ.get("NOTIFICATION_MOVEMENT_THRESHOLD_METERS", "50")
    try:
        return float(raw)
    except ValueError:
        return 50.0


def get_enabled_ser_providers() -> list[str]:
    """
    Return the list of enabled SER ticket provider codes from ENABLED_SER_PROVIDERS.

    Parses the comma-separated string into lowercase codes. Unlike
    get_enabled_brands(), values are plain strings rather than a domain enum,
    since SER ticket provider codes aren't modeled as one. Default is
    ["elparking"] when ENABLED_SER_PROVIDERS is not set — ElParking is meant
    to be on by default, unlike brands (which default to "generic").
    """
    raw = os.environ.get("ENABLED_SER_PROVIDERS", "elparking")
    return [code.strip().lower() for code in raw.split(",") if code.strip()]


def get_elparking_base_url() -> str:
    """
    Return the ElParking API base URL from the ELPARKING_API_BASE_URL env var.

    There is deliberately no default value here. ElParking's real API base
    URL is not yet publicly known — the only documentation available when
    this was written shows a placeholder (https://api.example.com) — so every
    deployment that enables the elparking SER ticket provider must supply the
    real base URL explicitly via environment variable.

    Raises:
        RuntimeError: If ELPARKING_API_BASE_URL is not set.
    """
    url = os.environ.get("ELPARKING_API_BASE_URL")
    if not url:
        raise RuntimeError(
            "ELPARKING_API_BASE_URL environment variable is not set. "
            "Set it to ElParking's real API base URL before enabling the elparking SER ticket provider."
        )
    return url


def get_elparking_app_version() -> str:
    """
    Return the ep-app-version value ElParking's login API expects, from
    ELPARKING_APP_VERSION.

    Unlike the base URL, this has a sensible default (the version this
    integration started with) since it's meant to evolve over time as
    ElParking's app versioning does, not to gate whether the provider can
    be enabled at all.
    """
    return os.environ.get("ELPARKING_APP_VERSION", "26.2")


def get_google_client_id() -> str:
    """Return the Google OAuth2 client ID from environment."""
    value = os.environ.get("GOOGLE_CLIENT_ID")
    if not value:
        raise RuntimeError("GOOGLE_CLIENT_ID environment variable is not set")
    return value


def get_google_client_secret() -> str:
    """Return the Google OAuth2 client secret from environment."""
    value = os.environ.get("GOOGLE_CLIENT_SECRET")
    if not value:
        raise RuntimeError("GOOGLE_CLIENT_SECRET environment variable is not set")
    return value


def get_telegram_bot_token() -> str:
    """
    Return the Telegram bot token from the TELEGRAM_BOT_TOKEN env var.

    There is deliberately no default value here, mirroring
    get_elparking_base_url()'s pattern: a real bot token is obtained per
    deployment via @BotFather and must be supplied explicitly.

    Raises:
        RuntimeError: If TELEGRAM_BOT_TOKEN is not set.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN environment variable is not set. "
            "Create a bot via @BotFather and set its token before enabling Telegram notifications."
        )
    return token


def get_telegram_webhook_secret() -> str:
    """
    Return the Telegram webhook secret from the TELEGRAM_WEBHOOK_SECRET env var.

    Used to validate the X-Telegram-Bot-Api-Secret-Token header on incoming
    webhook requests. No default — every deployment must supply its own.

    Raises:
        RuntimeError: If TELEGRAM_WEBHOOK_SECRET is not set.
    """
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
    if not secret:
        raise RuntimeError(
            "TELEGRAM_WEBHOOK_SECRET environment variable is not set. "
            "Set it to the secret_token value registered via Telegram's setWebhook API."
        )
    return secret


def get_telegram_bot_username() -> str:
    """
    Return the Telegram bot's @username from the TELEGRAM_BOT_USERNAME env var.

    Needed to build the t.me deep link returned by the link-code endpoint.
    No default — every deployment must supply its own.

    Raises:
        RuntimeError: If TELEGRAM_BOT_USERNAME is not set.
    """
    username = os.environ.get("TELEGRAM_BOT_USERNAME")
    if not username:
        raise RuntimeError("TELEGRAM_BOT_USERNAME environment variable is not set.")
    return username


def get_jwt_secret() -> str:
    """Return the JWT signing secret from environment."""
    value = os.environ.get("JWT_SECRET")
    if not value:
        raise RuntimeError("JWT_SECRET environment variable is not set")
    return value


def get_google_redirect_uri() -> str:
    """Return the Google OAuth2 redirect URI from environment."""
    value = os.environ.get("GOOGLE_REDIRECT_URI")
    if not value:
        raise RuntimeError("GOOGLE_REDIRECT_URI environment variable is not set")
    return value
