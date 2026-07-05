"""
Unit tests for SerTicketProviderRegistry.
"""

import pytest

from mobility_manager.infrastructure.ser_ticket_providers.registry import (
    SerTicketProviderRegistry,
)

try:
    import cryptography  # noqa: F401

    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from cryptography.fernet import Fernet

    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("ELPARKING_API_BASE_URL", "https://elparking.example.test")


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="cryptography not installed")
def test_elparking_registered_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENABLED_SER_PROVIDERS", raising=False)
    _set_required_env(monkeypatch)

    registry = SerTicketProviderRegistry()
    providers = registry.build_providers()

    assert "elparking" in providers
    from mobility_manager.infrastructure.ser_ticket_providers.elparking.provider import (
        ElParkingSerTicketProvider,
    )

    assert isinstance(providers["elparking"], ElParkingSerTicketProvider)


def test_elparking_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLED_SER_PROVIDERS", "")
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("ELPARKING_API_BASE_URL", raising=False)

    registry = SerTicketProviderRegistry()
    providers = registry.build_providers()

    assert "elparking" not in providers
    assert providers == {}


def test_missing_encryption_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLED_SER_PROVIDERS", "elparking")
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("ELPARKING_API_BASE_URL", "https://elparking.example.test")

    registry = SerTicketProviderRegistry()
    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
        registry.build_providers()


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="cryptography not installed")
def test_missing_base_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from cryptography.fernet import Fernet

    monkeypatch.setenv("ENABLED_SER_PROVIDERS", "elparking")
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.delenv("ELPARKING_API_BASE_URL", raising=False)

    registry = SerTicketProviderRegistry()
    with pytest.raises(RuntimeError, match="ELPARKING_API_BASE_URL"):
        registry.build_providers()


def test_unknown_provider_is_skipped_with_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("ENABLED_SER_PROVIDERS", "unknown_provider")

    registry = SerTicketProviderRegistry()
    with caplog.at_level("WARNING"):
        providers = registry.build_providers()

    assert providers == {}
    assert "unknown_provider" in caplog.text
