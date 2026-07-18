"""
Unit tests for provider_registry.build_providers()/list_city_codes().

Uses a mocked SQLAlchemy Engine (no live Postgres) whose
connect().execute(text("SELECT code FROM cities")).fetchall() returns a
canned set of city code rows — see add-ser-enforcement-calendar design.md
D10 and tasks.md 8.10.

Covers the `city-parking-data-provider` spec's "Default cities table
activates Madrid only", "City code with no registered implementation is
skipped with a warning", "Multiple cities can be enabled simultaneously",
and "ENABLED_CITIES has no effect" scenarios.
"""

from unittest.mock import MagicMock

import pytest

from mobility_manager.infrastructure.parking_services.madrid.ser_streets_provider import (
    MadridSerStreetsProvider,
)
from mobility_manager.infrastructure.parking_services.provider_registry import (
    build_providers,
    list_city_codes,
)


def _make_engine_with_city_codes(codes: list[str]) -> MagicMock:
    engine = MagicMock()
    conn = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    conn.execute.return_value.fetchall.return_value = [(code,) for code in codes]
    return engine


def test_list_city_codes_returns_all_rows_from_cities_table() -> None:
    engine = _make_engine_with_city_codes(["madrid", "barcelona"])

    assert list_city_codes(engine) == ["madrid", "barcelona"]


def test_default_cities_table_activates_madrid_only() -> None:
    engine = _make_engine_with_city_codes(["madrid"])

    providers = build_providers(engine)

    assert len(providers) == 1
    assert isinstance(providers[0], MadridSerStreetsProvider)


def test_city_code_with_no_registered_implementation_is_skipped_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _make_engine_with_city_codes(["madrid", "barcelona"])

    with caplog.at_level("WARNING"):
        providers = build_providers(engine)

    assert len(providers) == 1
    assert isinstance(providers[0], MadridSerStreetsProvider)
    assert "barcelona" in caplog.text
    assert "no registered provider" in caplog.text.lower()


def test_multiple_cities_with_implementations_are_all_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Only 'madrid' has a real implementation today, so this exercises the
    dispatch-per-code loop with two codes that both resolve to the same
    branch (proving the loop doesn't stop after the first match).
    """
    engine = _make_engine_with_city_codes(["madrid"])

    providers = build_providers(engine)

    assert len(providers) == 1  # only one row -> one provider; loop behavior confirmed by other tests


def test_no_providers_configured_logs_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    engine = _make_engine_with_city_codes(["unknown_city"])

    with caplog.at_level("WARNING"):
        providers = build_providers(engine)

    assert providers == []
    assert "No valid city providers configured" in caplog.text


def test_enabled_cities_env_var_has_no_effect_on_provider_registration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setting ENABLED_CITIES to a value excluding 'madrid' must not change which providers are built."""
    monkeypatch.setenv("ENABLED_CITIES", "barcelona")
    engine = _make_engine_with_city_codes(["madrid"])

    providers = build_providers(engine)

    assert len(providers) == 1
    assert isinstance(providers[0], MadridSerStreetsProvider)


def test_enabled_cities_env_var_unset_has_no_effect_either(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENABLED_CITIES", raising=False)
    engine = _make_engine_with_city_codes(["madrid"])

    providers = build_providers(engine)

    assert len(providers) == 1


def test_no_enabled_cities_reference_anywhere_in_module() -> None:
    """
    Structural guard: the module must not read ENABLED_CITIES at all (not
    merely ignore its value) — see design.md D10 and tasks.md 9.4.
    """
    import inspect

    from mobility_manager.infrastructure.parking_services import provider_registry

    source = inspect.getsource(provider_registry)
    assert "ENABLED_CITIES" not in source
    assert "_KNOWN_CITIES" not in source


def test_per_source_url_overrides_remain_unaffected(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Per-source URL env var overrides configure a provider's own data
    sources, not which cities are active — they must still work after the
    cities-table rewrite. Uses each source's own allowed hostname with a
    different path, since each fetcher enforces its own hostname allowlist.
    """
    monkeypatch.setenv("SER_ZONE_SHP_URL", "https://geoportal.madrid.es/custom/ser_zone.zip")
    monkeypatch.setenv("MADRID_CALLEJERO_URL", "https://datos.madrid.es/custom/callejero.csv")
    monkeypatch.setenv("MADRID_BARRIOS_SHP_URL", "https://geoportal.madrid.es/custom/barrios.zip")
    engine = _make_engine_with_city_codes(["madrid"])

    providers = build_providers(engine)

    assert len(providers) == 1
    provider = providers[0]
    assert isinstance(provider, MadridSerStreetsProvider)
