"""
Application: notification templates.

A small, hand-rolled per-language string dict covering the notification
kinds this system defines (vehicle-moved, Telegram-link confirmation,
SER-ticket-required) — not a general-purpose i18n framework (no .po/.mo
compilation, no gettext dependency). This handful of message kinds doesn't
justify that infrastructure (see design.md decision 6).

SUPPORTED_LANGUAGES is exported as the single source of truth shared between
rendering (falls back to "en" for None/unrecognized) and PUT /preferences'
notification_language validation, so the two can't silently drift apart.
"""

_TEMPLATES: dict[str, dict[str, str]] = {
    "en": {
        "vehicle_moved": "Your car with plate {plate} is now located here.",
        "telegram_linked": "✅ Linked!",
        "ser_ticket_required": "Your car with plate {plate} is in SER zone {zone_number} — you need to create a parking ticket.",
    },
    "es": {
        "vehicle_moved": "Tu coche con matrícula {plate} está ahora aquí.",
        "telegram_linked": "✅ ¡Vinculado!",
        "ser_ticket_required": "Tu coche con matrícula {plate} está en la zona SER {zone_number} — necesitas crear un tique de estacionamiento.",
    },
}

_DEFAULT_LANGUAGE = "en"

SUPPORTED_LANGUAGES = frozenset(_TEMPLATES.keys())


def render(key: str, language: str | None, **kwargs: str) -> str:
    """
    Render the template for `key` in `language`, substituting `kwargs`.

    Falls back to the default language ("en") when `language` is None or not
    among the supported set, rather than raising.
    """
    lang = language if language in _TEMPLATES else _DEFAULT_LANGUAGE
    return _TEMPLATES[lang][key].format(**kwargs)
