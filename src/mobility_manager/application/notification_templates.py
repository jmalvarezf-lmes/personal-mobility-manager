"""
Application: notification templates.

A filesystem-based Jinja2 template catalog covering the notification kinds
this system defines — not a general-purpose i18n framework (no .po/.mo
compilation, no gettext dependency, no pluralization support). It covers
exactly the notification kinds this system defines.

Templates live under `templates/<type_key>/<language>.txt.j2`: one directory
per notification kind, one file per supported language. Directory names for
preference-gated kinds match the `notification_types` catalog's `key`
exactly (e.g. `location_moved`, `ser_zone_ticket_required`), so the template
catalog and the preferences catalog share one identity instead of two
independently-maintained ones. `telegram_linked` follows the same directory
convention despite having no catalog row, since it's sent unconditionally.

SUPPORTED_LANGUAGES is derived from the template catalog itself: at import
time, every type directory's set of language files is compared, and import
fails fast if any type directory is missing a language present in another
— see `validate_language_coverage`. SUPPORTED_LANGUAGES is exported as the
single source of truth shared between rendering (falls back to the default
language for None/unrecognized) and PUT /preferences' notification_language
validation, so the two can't silently drift apart.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping
from collections.abc import Set as AbstractSet

from jinja2 import BaseLoader, Environment, PackageLoader, StrictUndefined

_DEFAULT_LANGUAGE = "en"

# Matches template names as returned by a Jinja2 loader's list_templates(),
# e.g. "location_moved/en.txt.j2" -> type_key="location_moved", language="en".
_TEMPLATE_NAME_RE = re.compile(r"^(?P<type_key>[^/]+)/(?P<language>[^/]+)\.txt\.j2$")


class TemplateCoverageError(RuntimeError):
    """Raised when the template catalog's per-type language coverage is inconsistent."""


def collect_language_coverage(loader: BaseLoader) -> dict[str, set[str]]:
    """
    Scan `loader` and group the language codes found per notification type.

    Any template name not matching `<type_key>/<language>.txt.j2` is
    ignored. Accepts any Jinja2 `BaseLoader` (`PackageLoader`,
    `FileSystemLoader`, ...) so this can be exercised against a throwaway
    fixture tree in tests, not just the real packaged catalog.
    """
    coverage: dict[str, set[str]] = defaultdict(set)
    for name in loader.list_templates():
        match = _TEMPLATE_NAME_RE.match(name)
        if match is None:
            continue
        coverage[match.group("type_key")].add(match.group("language"))
    return dict(coverage)


def validate_language_coverage(coverage: Mapping[str, AbstractSet[str]]) -> frozenset[str]:
    """
    Validate that every notification type has an identical set of languages.

    Returns the common language set as a frozenset on success. Raises
    `TemplateCoverageError` naming the offending type and its missing
    language(s) if any type's coverage differs from the union of all types'
    coverage, rather than deferring discovery to the first `render()` call
    for that (type, language) combination.
    """
    if not coverage:
        raise TemplateCoverageError("No notification templates found in the template catalog.")

    all_languages: set[str] = set()
    for languages in coverage.values():
        all_languages |= set(languages)

    for type_key, languages in coverage.items():
        missing = all_languages - set(languages)
        if missing:
            raise TemplateCoverageError(
                f"Notification template type '{type_key}' is missing template(s) for "
                f"language(s): {', '.join(sorted(missing))}"
            )

    return frozenset(all_languages)


_loader = PackageLoader("mobility_manager", "application/templates")
_env = Environment(
    loader=_loader,
    # Output is plain text delivered to Telegram/push channels, not HTML —
    # autoescaping would incorrectly HTML-entity-escape values like a plate
    # or an SER zone number. Stated explicitly rather than relied upon
    # implicitly (see design.md decision 5).
    autoescape=False,  # noqa: S701
    # A missing kwarg must raise (jinja2.UndefinedError), not silently
    # render as an empty string — the default lenient `Undefined` class
    # would otherwise regress the fail-fast KeyError behavior the old
    # str.format(**kwargs) implementation had for the same case.
    undefined=StrictUndefined,
)

SUPPORTED_LANGUAGES: frozenset[str] = validate_language_coverage(collect_language_coverage(_loader))


def render(type_key: str, language: str | None, **kwargs: str | bool) -> str:
    """
    Render the template for `type_key` in `language`, substituting `kwargs`.

    Falls back to the default language when `language` is None or not
    among SUPPORTED_LANGUAGES, rather than raising. Most templates only
    interpolate `str` values; `bool` is additionally accepted for kwargs a
    template branches on via Jinja `{% if %}` rather than interpolates
    directly (e.g. `ser_ticket_creation_failed`'s `possibly_created`).
    """
    lang = language if language in SUPPORTED_LANGUAGES else _DEFAULT_LANGUAGE
    template = _env.get_template(f"{type_key}/{lang}.txt.j2")
    return template.render(**kwargs)
