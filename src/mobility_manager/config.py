"""
Application configuration loaded from environment variables.
"""

import contextlib
import logging
import os
import re
from datetime import timedelta
from typing import Any, Final

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_LEGACY_NOTIFICATION_THRESHOLD_ENV_VAR = "NOTIFICATION_MOVEMENT_THRESHOLD_METERS"
_NOTIFICATION_THRESHOLD_ENV_VAR = "DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS"

# Single source of truth for the server-side session lifetime, shared by
# CreateSession (sets the DB row's expires_at) and auth.py (sets the JWT's
# exp claim and the cookie's max_age) — see add-session-revocation 4R review
# fix 4. Deliberately not env-configurable: this is a de-duplication, not a
# new tunable.
SESSION_LIFETIME: Final[timedelta] = timedelta(hours=24)


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


def get_event_publisher_max_workers() -> int:
    """Return InMemoryEventPublisher's async-dispatch thread pool size from environment."""
    raw = os.environ.get("EVENT_PUBLISHER_MAX_WORKERS", "4")
    try:
        return int(raw)
    except ValueError:
        return 4


def get_ambient_label_poll_interval_minutes() -> int:
    """Return the ambient label scheduler's tick interval in minutes from environment."""
    raw = os.environ.get("AMBIENT_LABEL_POLL_INTERVAL_MINUTES", "60")
    try:
        return int(raw)
    except ValueError:
        return 60


def get_ambient_label_retry_cooldown_hours() -> int:
    """
    Return the cooldown (in hours) before an inconclusive (`not_found`/`error`)
    ambient label lookup is retried, from environment.
    """
    raw = os.environ.get("AMBIENT_LABEL_RETRY_COOLDOWN_HOURS", "24")
    try:
        return int(raw)
    except ValueError:
        return 24


def get_ambient_label_request_delay_seconds() -> int:
    """
    Return the delay (in seconds) the ambient label scheduler waits between
    consecutive DGT requests within a single tick, from environment.
    """
    raw = os.environ.get("AMBIENT_LABEL_REQUEST_DELAY_SECONDS", "5")
    try:
        return int(raw)
    except ValueError:
        return 5


def get_default_notification_movement_threshold_meters() -> float:
    """
    Return the fallback movement-distance threshold (metres) used to resolve
    a user's effective `threshold_m` for a notification type when their
    per-type `config` doesn't specify one.

    No longer read directly by the notification event handlers — see
    notification-type-preferences design.md decision 3. This is a live,
    restart-only-tunable default: changing it takes effect immediately for
    every user who hasn't explicitly overridden `threshold_m`, without a
    data migration, since stored preference rows never snapshot this value.

    Warns if the old NOTIFICATION_MOVEMENT_THRESHOLD_METERS env var is still
    set while the new DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS is not
    — otherwise a deployment that hasn't renamed it silently reverts to the
    `50` default with no signal that its previously-configured value is
    being ignored.
    """
    if os.environ.get(_LEGACY_NOTIFICATION_THRESHOLD_ENV_VAR) and not os.environ.get(_NOTIFICATION_THRESHOLD_ENV_VAR):
        logger.warning(
            "%s is set but %s is not — the old variable is no longer read and this deployment is silently "
            "using the default of 50 metres. Rename %s to %s.",
            _LEGACY_NOTIFICATION_THRESHOLD_ENV_VAR,
            _NOTIFICATION_THRESHOLD_ENV_VAR,
            _LEGACY_NOTIFICATION_THRESHOLD_ENV_VAR,
            _NOTIFICATION_THRESHOLD_ENV_VAR,
        )

    raw = os.environ.get(_NOTIFICATION_THRESHOLD_ENV_VAR, "50")
    try:
        return float(raw)
    except ValueError:
        return 50.0


def resolve_effective_threshold(config: dict[str, Any]) -> float:
    """
    Resolve a notification type's effective `threshold_m` from a stored
    `config` dict, falling back to get_default_notification_movement_threshold_meters()
    when the field is absent.

    Shared by NotificationDispatchHandler and SerTicketNotificationTriggerHandler, which
    previously each implemented an identical private `_effective_threshold`
    — see notification-type-preferences review findings R2-001.
    """
    threshold_m = config.get("threshold_m")
    if threshold_m is not None:
        return float(threshold_m)
    return get_default_notification_movement_threshold_meters()


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


_DEFAULT_HOLIDAY_ICAL_URL = (
    "https://calendar.google.com/calendar/ical/es.spain%23holiday%40group.v.calendar.google.com/public/basic.ics"
)


def get_holiday_calendar_url() -> str:
    """
    Return the public holiday calendar iCal feed URL from HOLIDAY_CALENDAR_URL,
    or the Google Calendar default if unset.

    Unlike get_elparking_base_url()/get_telegram_bot_token(), this has a
    real, working default (Google's public Spain national holiday
    calendar) — see add-ser-enforcement-calendar design.md D7 — so there is
    no RuntimeError-if-missing gate here; every deployment gets a working
    holiday feed out of the box, overridable via env var.

    The default literal is duplicated (not imported) from
    google_calendar_provider.DEFAULT_HOLIDAY_ICAL_URL: config.py is a
    low-level module and must not depend on infrastructure, mirroring how
    provider_registry.py's SER_ZONE_SHP_URL/MADRID_CALLEJERO_URL/
    MADRID_BARRIOS_SHP_URL overrides read their provider's own DEFAULT_*
    constant directly rather than config.py importing it — the provider
    owns its own default.
    """
    return os.environ.get("HOLIDAY_CALENDAR_URL", _DEFAULT_HOLIDAY_ICAL_URL)


def get_holiday_refresh_interval_hours() -> int:
    """
    Return the holiday refresh scheduler's interval in hours from
    HOLIDAY_REFRESH_INTERVAL_HOURS, or 4380 (6 months) if unset/invalid.

    Mirrors get_ingestion_interval_hours()'s int-with-fallback style.
    """
    raw = os.environ.get("HOLIDAY_REFRESH_INTERVAL_HOURS", "4380")
    try:
        return int(raw)
    except ValueError:
        return 4380


def get_ser_zone_containment_tolerance_cm() -> int:
    """
    Return the SER zone containment tolerance in centimetres from
    SER_ZONE_CONTAINMENT_TOLERANCE_CM, or 50 if unset/invalid.

    Compensates for GPS positioning error in SerZone.contains() checks (see
    add-ser-zone-containment-tolerance design.md D3): a location within this
    distance of a zone's polygon boundary is treated as contained. This is a
    technical/operational tuning knob, not a per-user preference — it is not
    exposed through any user-facing API or preference storage.

    Mirrors get_vehicle_poll_interval_minutes()'s int-with-fallback style.
    """
    raw = os.environ.get("SER_ZONE_CONTAINMENT_TOLERANCE_CM", "50")
    try:
        return int(raw)
    except ValueError:
        return 50


def get_ser_ticket_creation_zone_change_floor_meters() -> int:
    """
    Return the GPS-noise floor in meters from
    SER_TICKET_CREATION_ZONE_CHANGE_FLOOR_METERS, or 10 if unset/invalid.

    Precedes SerTicketCreationTriggerHandler's zone-transition gate (see
    change-ser-auto-ticket-zone-gate design.md D2): movement below this floor
    since the vehicle's previous recorded location is treated as GPS jitter,
    not real movement, and skips both zone lookups entirely. This is a
    technical/operational tuning knob, not a per-user preference — distinct
    from the notification handler's user-configurable, much larger movement
    threshold (see resolve_effective_threshold), which answers a different
    question ("has the user moved enough to want a reminder").

    The default was raised from 5 to 10 meters after a 4R review found the
    original value assumed events arrive no faster than the 5-minute default
    poll interval — an assumption that doesn't hold for
    `POST /vehicles/{token}/location`, which is rate-limited to 60/minute
    (up to ~1 event/second) independent of the poll interval. Ordinary GPS
    jitter routinely exceeds 5m, so a vehicle near a zone boundary pushing at
    that rate could register a zone-transition on nearly every event. 10
    meters is still far tighter than the notification handler's 50m default,
    while giving a larger buffer against jitter; the push endpoint also now
    rate-limits per vehicle token to 1/minute (see the `vehicle-location-push`
    capability) as a second, independent mitigation.

    Mirrors get_ser_zone_containment_tolerance_cm()'s int-with-fallback
    style.
    """
    raw = os.environ.get("SER_TICKET_CREATION_ZONE_CHANGE_FLOOR_METERS", "10")
    try:
        return int(raw)
    except ValueError:
        return 10


def get_session_cleanup_retention_days() -> int:
    """
    Return the session cleanup retention window in days from
    SESSION_CLEANUP_RETENTION_DAYS, or 30 if unset/invalid/negative.

    Controls how long a revoked-or-expired `sessions` row survives before
    the cleanup job purges it. Mirrors get_vehicle_poll_interval_minutes()'s
    int-with-fallback style, plus a lower-bound guard: a negative value
    would push CleanupExpiredSessions's cutoff into the future, causing
    delete_older_than to purge every session (including active ones) —
    see add-session-revocation 4R review fix 2.
    """
    raw = os.environ.get("SESSION_CLEANUP_RETENTION_DAYS", "30")
    try:
        value = int(raw)
    except ValueError:
        return 30

    if value < 0:
        logger.warning(
            "SESSION_CLEANUP_RETENTION_DAYS is negative (%s), which would delete all active sessions. "
            "Falling back to the default of 30 days.",
            value,
        )
        return 30

    return value


def get_session_cleanup_interval_hours() -> int:
    """
    Return the session cleanup job's run interval in hours from
    SESSION_CLEANUP_INTERVAL_HOURS, or 24 if unset/invalid.

    Mirrors get_ingestion_interval_hours()'s int-with-fallback style.
    """
    raw = os.environ.get("SESSION_CLEANUP_INTERVAL_HOURS", "24")
    try:
        return int(raw)
    except ValueError:
        return 24


def get_otel_endpoint() -> str | None:
    """
    Return the OTLP exporter endpoint from OTEL_EXPORTER_OTLP_ENDPOINT, or
    None if unset.

    This is the single activation check for OpenTelemetry observability
    (see add-opentelemetry-observability design.md decision 3): real
    TracerProvider/MeterProvider and auto-instrumentation are only wired up
    in app.py's lifespan when this returns a value. Manual span/metric
    calls elsewhere in the app are always safe to call unconditionally —
    OTel's API is a no-op by default until a real provider is registered.
    """
    return os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or None
