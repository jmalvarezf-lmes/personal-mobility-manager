"""Unit tests for the notification_templates rendering mechanism."""

from mobility_manager.application.notification_templates import (
    SUPPORTED_LANGUAGES,
    render,
)


def test_renders_known_kind_in_supported_language_with_substitution() -> None:
    text = render("vehicle_moved", "es", plate="1234ABC")
    assert text == "Tu coche con matrícula 1234ABC está ahora aquí."


def test_renders_known_kind_in_english() -> None:
    text = render("vehicle_moved", "en", plate="1234ABC")
    assert text == "Your car with plate 1234ABC is now located here."


def test_none_language_falls_back_to_default() -> None:
    text = render("vehicle_moved", None, plate="1234ABC")
    assert text == "Your car with plate 1234ABC is now located here."


def test_unrecognized_language_falls_back_to_default() -> None:
    text = render("vehicle_moved", "fr", plate="1234ABC")
    assert text == "Your car with plate 1234ABC is now located here."


def test_telegram_linked_template_has_no_substitution() -> None:
    assert render("telegram_linked", "en") == "✅ Linked!"
    assert render("telegram_linked", "es") == "✅ ¡Vinculado!"


def test_supported_languages_contains_en_and_es() -> None:
    assert "en" in SUPPORTED_LANGUAGES
    assert "es" in SUPPORTED_LANGUAGES
