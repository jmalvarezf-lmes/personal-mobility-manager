"""
Unit tests for BrandRegistry.
"""
import pytest

from mobility_manager.infrastructure.vehicle_providers.brand_registry import (
    BrandRegistry,
)

try:
    import cryptography  # noqa: F401

    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False


def test_generic_only_returns_empty_list(monkeypatch) -> None:
    monkeypatch.setenv("ENABLED_BRANDS", "generic")
    registry = BrandRegistry()
    providers = registry.build_pull_providers()
    assert providers == []


def test_unknown_brand_is_skipped(monkeypatch, caplog) -> None:
    monkeypatch.setenv("ENABLED_BRANDS", "unknown_brand")
    registry = BrandRegistry()
    with caplog.at_level("WARNING"):
        providers = registry.build_pull_providers()
    assert providers == []
    assert "unknown_brand" in caplog.text


def test_toyota_without_encryption_key_raises(monkeypatch) -> None:
    monkeypatch.setenv("ENABLED_BRANDS", "toyota")
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    registry = BrandRegistry()
    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
        registry.build_pull_providers()


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="cryptography not installed")
def test_toyota_with_encryption_key_returns_provider(monkeypatch) -> None:
    """With a valid key set, Toyota provider should be instantiated."""
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENABLED_BRANDS", "toyota")
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    registry = BrandRegistry()
    providers = registry.build_pull_providers()
    assert len(providers) == 1
    from mobility_manager.infrastructure.vehicle_providers.toyota.location_provider import (
        ToyotaLocationProvider,
    )

    assert isinstance(providers[0], ToyotaLocationProvider)


@pytest.mark.skipif(not _CRYPTO_AVAILABLE, reason="cryptography not installed")
def test_mixed_brands_unknown_skipped_toyota_added(monkeypatch, caplog) -> None:
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENABLED_BRANDS", "toyota,unknown_brand")
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    registry = BrandRegistry()
    with caplog.at_level("WARNING"):
        providers = registry.build_pull_providers()
    assert len(providers) == 1
    assert "unknown_brand" in caplog.text
