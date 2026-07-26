"""
Application: datetime formatting helpers.

A small pure helper so notification-rendering event handlers can convert a
UTC-aware `datetime` into a user's configured display timezone before
passing it into a Jinja2 template as an already-formatted string — keeping
the templates themselves free of timezone logic (see notification-templates
spec.md and add-ser-ticket-auto-creation design.md decision 5).
"""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_UTC_ZONE = ZoneInfo("UTC")
_DISPLAY_FORMAT = "%Y-%m-%d %H:%M %Z"


def format_local_datetime(dt: datetime, timezone: str | None) -> str:
    """
    Format `dt` (a UTC-aware datetime) into `timezone`'s local time.

    Falls back to UTC when `timezone` is None or not a recognized IANA zone
    (defensive — PUT /preferences already validates it against
    `zoneinfo.available_timezones()`, so an unrecognized value here should
    never happen in practice, but this helper must never raise).
    """
    zone = _UTC_ZONE
    if timezone is not None:
        try:
            zone = ZoneInfo(timezone)
        except ZoneInfoNotFoundError:
            zone = _UTC_ZONE

    return dt.astimezone(zone).strftime(_DISPLAY_FORMAT)
