"""Unit tests for the notification_templates rendering mechanism."""

from pathlib import Path

import pytest
from jinja2 import FileSystemLoader
from jinja2.exceptions import TemplateNotFound, UndefinedError

from mobility_manager.application.notification_templates import (
    SUPPORTED_LANGUAGES,
    TemplateCoverageError,
    collect_language_coverage,
    render,
    validate_language_coverage,
)


def test_renders_known_kind_in_supported_language_with_substitution() -> None:
    text = render("location_moved", "es", plate="1234ABC")
    assert text == "Tu coche con matrícula 1234ABC está ahora aquí."


def test_renders_known_kind_in_english() -> None:
    text = render("location_moved", "en", plate="1234ABC")
    assert text == "Your car with plate 1234ABC is now located here."


def test_none_language_falls_back_to_default() -> None:
    text = render("location_moved", None, plate="1234ABC")
    assert text == "Your car with plate 1234ABC is now located here."


def test_unrecognized_language_falls_back_to_default() -> None:
    text = render("location_moved", "fr", plate="1234ABC")
    assert text == "Your car with plate 1234ABC is now located here."


def test_telegram_linked_template_has_no_substitution() -> None:
    assert render("telegram_linked", "en") == "✅ Linked!"
    assert render("telegram_linked", "es") == "✅ ¡Vinculado!"


def test_supported_languages_contains_en_and_es() -> None:
    assert "en" in SUPPORTED_LANGUAGES
    assert "es" in SUPPORTED_LANGUAGES


def test_ser_zone_ticket_required_template_renders_in_spanish() -> None:
    text = render("ser_zone_ticket_required", "es", plate="1234ABC", zone_number="163")
    assert text == "Tu coche con matrícula 1234ABC está en la zona SER 163 — necesitas crear un tique de estacionamiento."


def test_ser_zone_ticket_required_template_renders_in_english() -> None:
    text = render("ser_zone_ticket_required", "en", plate="1234ABC", zone_number="163")
    assert text == "Your car with plate 1234ABC is in SER zone 163 — you need to create a parking ticket."


def test_ser_zone_ticket_required_template_falls_back_to_default_language() -> None:
    text = render("ser_zone_ticket_required", None, plate="1234ABC", zone_number="163")
    assert text == "Your car with plate 1234ABC is in SER zone 163 — you need to create a parking ticket."


# ---------------------------------------------------------------------------
# render() error behavior — missing kwargs and unknown type_key
# ---------------------------------------------------------------------------


def test_render_raises_when_a_required_kwarg_is_missing() -> None:
    """
    A missing required kwarg must raise, not silently render empty text.

    The Jinja2 Environment uses StrictUndefined precisely so this fails
    loudly (jinja2.UndefinedError) instead of interpolating an empty
    string — matching the fail-fast KeyError the old str.format(**kwargs)
    implementation raised for the same case.
    """
    with pytest.raises(UndefinedError):
        render("location_moved", "en")


def test_render_raises_when_a_required_kwarg_is_missing_for_ser_zone_ticket_required() -> None:
    with pytest.raises(UndefinedError):
        render("ser_zone_ticket_required", "en", plate="1234ABC")


def test_render_raises_for_unknown_type_key() -> None:
    """
    An unknown type_key (no matching template directory) must raise, not
    return a default/empty string. Pins the current TemplateNotFound
    behavior — this is a programmer-error/internal-boundary case (an
    unrecognized type_key is never user input), analogous to the raw
    KeyError the old dict-based implementation would have raised for the
    same case. No need for a custom exception type here.
    """
    with pytest.raises(TemplateNotFound):
        render("not_a_real_notification_kind", "en")


# ---------------------------------------------------------------------------
# Fail-fast language-coverage validation
# ---------------------------------------------------------------------------


def test_validate_language_coverage_raises_on_missing_language(tmp_path: Path) -> None:
    """
    A type directory missing one supported language's template file must
    cause catalog loading to raise, naming the type and the missing
    language — exercised here against a throwaway fixture tree rather than
    the real packaged catalog, per tasks.md 7.6.
    """
    (tmp_path / "kind_a").mkdir()
    (tmp_path / "kind_a" / "en.txt.j2").write_text("English kind_a")
    (tmp_path / "kind_a" / "es.txt.j2").write_text("Spanish kind_a")

    (tmp_path / "kind_b").mkdir()
    (tmp_path / "kind_b" / "en.txt.j2").write_text("English kind_b")
    # kind_b is missing its "es" template on purpose.

    loader = FileSystemLoader(str(tmp_path))
    coverage = collect_language_coverage(loader)

    with pytest.raises(TemplateCoverageError) as exc_info:
        validate_language_coverage(coverage)

    message = str(exc_info.value)
    assert "kind_b" in message
    assert "es" in message


def test_validate_language_coverage_succeeds_when_all_types_match(tmp_path: Path) -> None:
    (tmp_path / "kind_a").mkdir()
    (tmp_path / "kind_a" / "en.txt.j2").write_text("English kind_a")
    (tmp_path / "kind_a" / "es.txt.j2").write_text("Spanish kind_a")

    (tmp_path / "kind_b").mkdir()
    (tmp_path / "kind_b" / "en.txt.j2").write_text("English kind_b")
    (tmp_path / "kind_b" / "es.txt.j2").write_text("Spanish kind_b")

    loader = FileSystemLoader(str(tmp_path))
    coverage = collect_language_coverage(loader)

    assert validate_language_coverage(coverage) == frozenset({"en", "es"})
